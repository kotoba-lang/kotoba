"""Zeebe task handlers for site.etzhayyim.com Common Crawl orchestration.

Common Crawl acquisition stays artifact-first: download/graph/intel commands
produce files, and the write step is explicitly delegated to the domain ingest
path.  The BPMN process owns durable run/cursor state and read-after-write
verification for the site read models.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.ingest.core import (
    IngestArtifact,
    IngestRun,
    mark_run_finished,
    upsert_artifact,
    upsert_cursor,
    upsert_run,
)

ACTOR_DID = "did:web:site.etzhayyim.com"
SOURCE_ID = "common-crawl"
INGEST_FAMILY = "site"
BPMN_PROCESS_ID = "ingest_site_common_crawl_delta"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _data_dir(ccDataDir: str = "") -> Path:
    return Path(
        ccDataDir
        or os.environ.get("SITE_CC_DATA_DIR")
        or os.environ.get("CC_DATA_DIR")
        or "/Volumes/251220/CC/2603"
    )


def _repo_root() -> Path | None:
    configured = os.environ.get("SITE_CC_REPO_ROOT") or os.environ.get("REPO_ROOT")
    if configured:
        return Path(configured)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "00-contracts").exists() and (parent / "60-apps").exists():
            return parent
    return None


def _etzhayyim_binary() -> str:
    return os.environ.get("etzhayyim_BIN") or shutil.which("etzhayyim") or "etzhayyim"


def _run_command(args: list[str], *, timeout_sec: int, env: dict[str, str]) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
        check=False,
    )
    stdout = (proc.stdout or "")[-4000:]
    stderr = (proc.stderr or "")[-4000:]
    return {
        "ok": proc.returncode == 0,
        "returnCode": proc.returncode,
        "stdoutTail": stdout,
        "stderrTail": stderr,
        "command": args,
    }


def _artifact_stats(data_dir: Path) -> dict[str, Any]:
    graph_dir = data_dir / "graph"
    stats: dict[str, Any] = {
        "dataDir": str(data_dir),
        "graphSqlFiles": len(glob.glob(str(graph_dir / "did_batch_*.sql"))),
        "parquetPageFiles": len(glob.glob(str(data_dir / "parquet-rs" / "*_pages.parquet"))),
        "domainIntelExists": (graph_dir / "domain_intel.jsonl.gz").exists(),
        "knowledgeGraphExists": (graph_dir / "knowledge_graph.sql").exists(),
    }
    for key, path in {
        "domainIntelBytes": graph_dir / "domain_intel.jsonl.gz",
        "knowledgeGraphBytes": graph_dir / "knowledge_graph.sql",
    }.items():
        stats[key] = path.stat().st_size if path.exists() else 0
    return stats


def _record_artifacts(run_id: str, source_id: str, data_dir: Path, stats: dict[str, Any]) -> int:
    artifacts: list[IngestArtifact] = []
    graph_dir = data_dir / "graph"
    intel = graph_dir / "domain_intel.jsonl.gz"
    if intel.exists():
        artifacts.append(
            IngestArtifact(
                run_id=run_id,
                artifact_kind="domain_intel",
                source_id=source_id,
                uri=str(intel),
                byte_size=intel.stat().st_size,
                props={"format": "jsonl.gz"},
            )
        )
    for pattern, kind in (("did_batch_*.sql", "did_batch_sql"), ("*_pages.parquet", "pages_parquet")):
        base = graph_dir if kind == "did_batch_sql" else data_dir / "parquet-rs"
        files = sorted(base.glob(pattern))[:25]
        for file_path in files:
            artifacts.append(
                IngestArtifact(
                    run_id=run_id,
                    artifact_kind=kind,
                    source_id=source_id,
                    uri=str(file_path),
                    byte_size=file_path.stat().st_size,
                    props={"sampled": stats.get("graphSqlFiles", 0) > 25},
                )
            )
    for artifact in artifacts:
        upsert_artifact(artifact)
    return len(artifacts)


def _site_counts(crawl: str = "") -> dict[str, int]:
    out = {"pageTotal": 0, "jobTotal": 0, "crawlPageTotal": 0}
    kotoba = get_kotoba_client()

    # R0: Initial SELECT cnt from mv_site_page_total
    page_total_mv = kotoba.select_first_where(table="mv_site_page_total", column=None, value=None, columns=["cnt"])
    if page_total_mv:
        out["pageTotal"] = int(page_total_mv.get("cnt") or 0)
    else:
        # Fallback if mv_site_page_total does not exist or is empty
        out["pageTotal"] = int(kotoba.aggregate_where("vertex_page", "count", "*", None, None) or 0)

    # R0: Initial SELECT cnt from mv_site_job_total
    job_total_mv = kotoba.select_first_where(table="mv_site_job_total", column=None, value=None, columns=["cnt"])
    if job_total_mv:
        out["jobTotal"] = int(job_total_mv.get("cnt") or 0)
    else:
        # Fallback if mv_site_job_total does not exist or is empty
        out["jobTotal"] = int(kotoba.aggregate_where("vertex_collection_job", "count", "*", None, None) or 0)

    if crawl:
        out["crawlPageTotal"] = int(kotoba.aggregate_where("vertex_page", "count", "*", "crawl", crawl) or 0)
    return out


async def task_site_cc_create_run(
    runId: str = "",
    sourceId: str = SOURCE_ID,
    mode: str = "delta",
    requestedBy: str = "zeebe",
    inputJson: str = "",
    crawl: str = "CC-MAIN-2026-12",
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    run = IngestRun(
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        mode=mode or "delta",
        run_id=runId,
        status="running",
        bpmn_process_id=BPMN_PROCESS_ID,
        requested_by=requestedBy,
        input_json=inputJson or json.dumps({"crawl": crawl}, sort_keys=True),
    ).with_run_id()
    if bool(dryRun):
        return {
            "ok": True,
            "runId": run.run_id,
            "runVertexId": f"dry-run:{run.run_id}",
            "sourceId": run.source_id,
        }
    vid = await asyncio.to_thread(upsert_run, run)
    return {"ok": True, "runId": run.run_id, "runVertexId": vid, "sourceId": run.source_id}


def task_site_cc_plan(
    crawl: str = "CC-MAIN-2026-12",
    domainFilter: str = "",
    phases: str = "graph,intel,domain-ingest",
    limit: int = 0,
    minPages: int = 0,
    batchSize: int = 200,
    dryRun: bool = False,
    ccDataDir: str = "",
    **_: Any,
) -> dict[str, Any]:
    selected = [
        phase.strip()
        for phase in str(phases or "graph,intel,domain-ingest").split(",")
        if phase.strip()
    ]
    allowed = {"download", "graph", "intel", "domain-ingest"}
    bad = [phase for phase in selected if phase not in allowed]
    if bad:
        return {"ok": False, "error": f"unsupported phases: {','.join(bad)}"}
    data_dir = _data_dir(ccDataDir)
    plan = {
        "crawl": crawl,
        "domainFilter": domainFilter,
        "phases": selected,
        "limit": int(limit or 0),
        "minPages": int(minPages or 0),
        "batchSize": int(batchSize or 200),
        "dryRun": bool(dryRun),
        "dataDir": str(data_dir),
        "repoRoot": str(_repo_root() or ""),
    }
    return {"ok": True, "siteCcPlan": plan, "plannedShards": 1, "shardKey": f"{crawl}:{domainFilter or '*'}"}


async def task_site_cc_acquire_cursor(
    runId: str,
    sourceId: str = SOURCE_ID,
    shardKey: str = "",
    crawl: str = "CC-MAIN-2026-12",
    domainFilter: str = "",
    dryRun: bool = False,
    siteCcPlan: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    shard = shardKey or f"{crawl}:{domainFilter or '*'}"
    if bool(dryRun or (siteCcPlan or {}).get("dryRun")):
        return {"ok": True, "shardKey": shard, "cursorVertexId": f"dry-run:{shard}", "cursorValue": shard}
    expires = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor_vid = await asyncio.to_thread(
        upsert_cursor,
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        shard_key=shard,
        locked_by_run_id=runId,
        lock_expires_at=expires,
        status="locked",
    )
    return {"ok": True, "shardKey": shard, "cursorVertexId": cursor_vid, "cursorValue": shard}


async def task_site_cc_run_phase(
    phase: str,
    siteCcPlan: dict[str, Any] | None = None,
    timeoutSec: int = 21600,
    allowSubprocess: bool = False,
    **_: Any,
) -> dict[str, Any]:
    plan = siteCcPlan or {}
    selected = set(plan.get("phases") or [])
    if phase not in selected:
        return {"ok": True, "skipped": True, "phase": phase, "reason": "phase-not-selected"}
    if bool(plan.get("dryRun")):
        return {"ok": True, "skipped": True, "phase": phase, "reason": "dry-run"}
    if not allowSubprocess and not _truthy(os.environ.get("SITE_CC_EXEC_ENABLED")):
        return {
            "ok": False,
            "phase": phase,
            "error": "subprocess execution disabled; set allowSubprocess=true or SITE_CC_EXEC_ENABLED=1",
        }

    crawl = str(plan.get("crawl") or "CC-MAIN-2026-12")
    domain = str(plan.get("domainFilter") or "")
    args = [_etzhayyim_binary()]
    if phase == "download":
        args += ["common-crawler", "download", "--crawl", crawl, "--format", "wat", "--workers", "4"]
    elif phase == "graph":
        args += ["common-crawler", "graph", "--crawl", crawl, "--output", "parquet"]
        if domain:
            args += ["--domain", domain]
    elif phase == "intel":
        args += ["common-crawler", "intel", "--output", "jsonl"]
        if int(plan.get("limit") or 0) > 0:
            args += ["--limit", str(int(plan["limit"]))]
        if int(plan.get("minPages") or 0) > 0:
            args += ["--min-pages", str(int(plan["minPages"]))]
        if domain:
            args += ["--domain", domain]
    elif phase == "domain-ingest":
        args += [
            "domain-ingest",
            "common-crawl",
            "--source",
            "intel",
            "--batch-size",
            str(int(plan.get("batchSize") or 200)),
        ]
    else:
        return {"ok": False, "phase": phase, "error": f"unsupported phase: {phase}"}

    env = {**os.environ, "CC_DATA_DIR": str(plan.get("dataDir") or _data_dir())}
    repo_root = plan.get("repoRoot")
    if repo_root:
        env["SITE_CC_REPO_ROOT"] = str(repo_root)
    result = await asyncio.to_thread(_run_command, args, timeout_sec=int(timeoutSec), env=env)
    return {"phase": phase, **result}


async def task_site_cc_record_artifacts(
    runId: str,
    sourceId: str = SOURCE_ID,
    siteCcPlan: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    data_dir = _data_dir(str((siteCcPlan or {}).get("dataDir") or ""))
    stats = await asyncio.to_thread(_artifact_stats, data_dir)
    recorded = await asyncio.to_thread(_record_artifacts, runId, sourceId or SOURCE_ID, data_dir, stats)
    return {"ok": True, "artifactRecords": recorded, "artifactStats": stats}


async def task_site_cc_verify_visibility(
    crawl: str = "CC-MAIN-2026-12",
    artifactStats: dict[str, Any] | None = None,
    dryRun: bool = False,
    siteCcPlan: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    plan = siteCcPlan or {}
    artifact_stats = artifactStats or {}
    if bool(dryRun or plan.get("dryRun")):
        return {"ok": True, "verified": True, "pageTotal": 0, "domainTotal": 0}
    counts = await asyncio.to_thread(_site_counts, crawl)
    verified = bool(dryRun or plan.get("dryRun") or counts["pageTotal"] > 0 or artifact_stats.get("parquetPageFiles"))
    return {"ok": verified, "verified": verified, **counts}


async def task_site_cc_advance_cursor(
    runId: str,
    sourceId: str = SOURCE_ID,
    shardKey: str = "",
    verified: bool = False,
    artifactStats: dict[str, Any] | None = None,
    dryRun: bool = False,
    siteCcPlan: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    if not verified:
        return {"ok": False, "error": "verified=true required before cursor advance"}
    if bool(dryRun or (siteCcPlan or {}).get("dryRun")):
        return {"ok": True, "cursorVertexId": f"dry-run:{shardKey or 'common-crawl'}"}
    content_hash = json.dumps(artifactStats or {}, sort_keys=True, separators=(",", ":"))[:512]
    cursor_vid = await asyncio.to_thread(
        upsert_cursor,
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        shard_key=shardKey or "common-crawl",
        cursor_value=now_iso(),
        content_hash=content_hash,
        locked_by_run_id=runId,
        lock_expires_at=now_iso(),
        status="completed",
    )
    return {"ok": True, "cursorVertexId": cursor_vid}


async def task_site_cc_complete_run(
    runId: str,
    recordsRead: int = 0,
    recordsWritten: int = 0,
    recordsSkipped: int = 0,
    errorCount: int = 0,
    verified: bool = False,
    artifactStats: dict[str, Any] | None = None,
    dryRun: bool = False,
    siteCcPlan: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    status = "completed" if verified and not errorCount else "degraded"
    if bool(dryRun or (siteCcPlan or {}).get("dryRun")):
        return {"ok": True, "status": status}
    await asyncio.to_thread(
        mark_run_finished,
        runId,
        status=status,
        records_read=recordsRead,
        records_written=recordsWritten,
        records_skipped=recordsSkipped,
        error_count=errorCount,
        output={"verified": verified, "artifactStats": artifactStats or {}},
    )
    return {"ok": True, "status": status}

"""Murakumo cell for the yabai Tor/Torrent CTI persistence path.

The cell runs as a LAN API worker backed by Kotoba Datomic. Jobs and per-step
checkpoints are datoms in a dedicated graph; there is no local SQLite queue.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import (
    KotobaDatomicClient,
    KotobaTransactError,
    edn_str,
    get_kotoba_client,
    to_tx_edn,
)

ACTOR_DID = "did:web:etzhayyim.com:actor:yabai"
CELL_NAME = "YabaiTorTorrentCtiPersistenceCell"
QUEUE_GRAPH = os.environ.get("YABAI_QUEUE_GRAPH", "etzhayyim/yabai/cti-persistence-queue")
NS_JOB = "yabai.job"
NS_CP = "yabai.checkpoint"


def _repo_root() -> pathlib.Path:
    configured = os.environ.get("ETZHAYYIM_ROOT") or os.environ.get("ETZ_REPO") or os.environ.get("ETZHAYYIM_REPO")
    if configured:
        return pathlib.Path(configured).expanduser().resolve()
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "20-actors" / "yabai").exists():
            return parent
    raise RuntimeError("repository root not found for yabai actor")


def _state_dir(repo: pathlib.Path) -> pathlib.Path:
    configured = os.environ.get("YABAI_STATE_DIR")
    candidates = []
    if configured:
        candidates.append(pathlib.Path(configured).expanduser())
    candidates.extend([
        pathlib.Path("/var/lib/etzhayyim/yabai"),
        repo / "20-actors" / "yabai" / "out",
    ])
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-probe"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    raise RuntimeError("no writable yabai state directory")


def _guardrails() -> None:
    rw_url = os.environ.get("RW_URL", "")
    if "runpod" in rw_url.lower() or shutil.which("runpod"):
        raise RuntimeError("refusing yabai Murakumo cell on runpod/RisingWave runtime")


async def _run(cmd: list[str], cwd: pathlib.Path, env: dict[str, str]) -> dict[str, Any]:
    proc = await asyncio.to_thread(
        subprocess.run,
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _append_marker(path: pathlib.Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _now() -> int:
    return int(time.time())


def _client() -> KotobaDatomicClient:
    return get_kotoba_client()


def _tx(client: KotobaDatomicClient, entities: list[dict[str, Any]], note: str) -> None:
    client.transact(to_tx_edn(entities, [note]), graph=QUEUE_GRAPH)


def _strip(ent: Any, ns: str) -> dict[str, Any]:
    if not isinstance(ent, dict):
        return {}
    prefix = f":{ns}/"
    out = {}
    for key, val in ent.items():
        k = str(key)
        col = k[len(prefix):] if k.startswith(prefix) else k.lstrip(":")
        out[col.replace("-", "_")] = val
    return out


def _pull_by_attr(ns: str, attr: str, value: str) -> str:
    return f"[:find (pull ?e [*]) :where [?e :{ns}/{attr} {edn_str(value)}]]"


def _all_jobs_query() -> str:
    return f"[:find (pull ?e [*]) :where [?e :{NS_JOB}/id _]]"


def _entity(item: Any, ns: str) -> dict[str, Any]:
    ent = item[0] if isinstance(item, (list, tuple)) and item else item
    return _strip(ent, ns)


def enqueue_job(
    *,
    kind: str = "persist",
    payload: dict[str, Any] | None = None,
    priority: int = 100,
    job_id: str | None = None,
    client: KotobaDatomicClient | None = None,
) -> str:
    c = client or _client()
    now = _now()
    jid = job_id or f"yabai-{now}-{uuid.uuid4().hex[:12]}"
    _tx(c, [{
        f":{NS_JOB}/id": jid,
        f":{NS_JOB}/kind": kind,
        f":{NS_JOB}/payload-json": json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
        f":{NS_JOB}/status": "pending",
        f":{NS_JOB}/priority": int(priority),
        f":{NS_JOB}/attempts": 0,
        f":{NS_JOB}/max-attempts": 5,
        f":{NS_JOB}/created-at": now,
        f":{NS_JOB}/updated-at": now,
    }], f"enqueue {jid}")
    return jid


def _checkpoint(client: KotobaDatomicClient, job_id: str, step: str, status: str, detail: dict[str, Any]) -> None:
    ts = time.time_ns()
    _tx(client, [{
        f":{NS_CP}/id": f"{job_id}:{step}:{ts}",
        f":{NS_CP}/job-id": job_id,
        f":{NS_CP}/step": step,
        f":{NS_CP}/status": status,
        f":{NS_CP}/ts": ts,
        f":{NS_CP}/detail-json": json.dumps(detail, ensure_ascii=False, sort_keys=True, default=str),
    }], f"checkpoint {job_id}/{step}/{status}")


def _load_job(client: KotobaDatomicClient, job_id: str) -> dict[str, Any] | None:
    rows = client.q(_pull_by_attr(NS_JOB, "id", job_id), graph=QUEUE_GRAPH)
    jobs = [_entity(row, NS_JOB) for row in rows]
    jobs = [job for job in jobs if job]
    if not jobs:
        return None
    jobs.sort(key=lambda job: int(job.get("updated_at") or 0), reverse=True)
    return jobs[0]


def _ready_jobs(client: KotobaDatomicClient) -> list[dict[str, Any]]:
    rows = client.q(_all_jobs_query(), graph=QUEUE_GRAPH)
    jobs = [_entity(row, NS_JOB) for row in rows]
    jobs = [job for job in jobs if job.get("status") == "pending"]
    jobs.sort(key=lambda job: (int(job.get("priority") or 100), int(job.get("created_at") or 0)))
    return jobs


def _job_counts(client: KotobaDatomicClient) -> dict[str, int]:
    rows = client.q(_all_jobs_query(), graph=QUEUE_GRAPH)
    counts: dict[str, int] = {}
    for row in rows:
        status = str(_entity(row, NS_JOB).get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _latest_jobs(client: KotobaDatomicClient, limit: int = 20) -> list[dict[str, Any]]:
    rows = client.q(_all_jobs_query(), graph=QUEUE_GRAPH)
    jobs = [_entity(row, NS_JOB) for row in rows]
    jobs = [job for job in jobs if job]
    jobs.sort(key=lambda job: int(job.get("updated_at") or 0), reverse=True)
    return jobs[:limit]


def _set_job_status(
    client: KotobaDatomicClient,
    job_id: str,
    status: str,
    *,
    attempts: int | None = None,
    last_error: str | None = None,
) -> None:
    ent: dict[str, Any] = {
        f":{NS_JOB}/id": job_id,
        f":{NS_JOB}/status": status,
        f":{NS_JOB}/updated-at": _now(),
    }
    if attempts is not None:
        ent[f":{NS_JOB}/attempts"] = attempts
    if last_error is not None:
        ent[f":{NS_JOB}/last-error"] = last_error
    _tx(client, [ent], f"job {job_id} -> {status}")


async def _run_pipeline(job_id: str, payload: dict[str, Any], client: KotobaDatomicClient) -> dict[str, Any]:
    _guardrails()
    repo = _repo_root()
    actor = repo / "20-actors" / "yabai"
    methods = actor / "methods"
    state = _state_dir(repo)
    marker_path = state / "cti-correlator-runs.ndjson"

    env = os.environ.copy()
    env.setdefault("KOTOBA_AUDIT_STRICT", "1")
    env.setdefault("PYTHONUTF8", "1")

    started = _now()
    record: dict[str, Any] = {
        "ts": started,
        "job_id": job_id,
        "cell": CELL_NAME,
        "actor_did": ACTOR_DID,
        "node": os.environ.get("ETZHAYYIM_NODE_NAME") or os.environ.get("ETZHAYYIM_NODE"),
        "mode": "live" if (env.get("YABAI_GRAPH_CID") and (env.get("KOTOBA_TOKEN") or env.get("KOTOBA_CACAO_B64"))) else "dry-run",
        "payload": payload,
        "checkpoint_graph": QUEUE_GRAPH,
        "boundary": "public Tor-exit indicators + case-bound BitTorrent evidence only; no de-anonymization",
    }

    steps = [
        ("ingest", [sys.executable, str(methods / "ingest.py")]),
        ("analyze", [sys.executable, str(methods / "analyze.py")]),
        ("transact", [sys.executable, str(methods / "transact.py")]),
    ]
    results = []
    for step_name, step_cmd in steps:
        _checkpoint(client, job_id, step_name, "started", {"cmd": step_cmd})
        result = await _run(step_cmd, actor, env)
        results.append(result)
        _checkpoint(client, job_id, step_name, "ok" if result["returncode"] == 0 else "failed", result)
        if result["returncode"] != 0:
            record.update({"ok": False, "failed_step": step_name, "results": results})
            _append_marker(marker_path, record)
            return record

    if record["mode"] != "live" and env.get("YABAI_REQUIRE_LIVE") == "1":
        record.update({"ok": False, "failed_step": "transact", "results": results, "error": "live credentials missing"})
        _append_marker(marker_path, record)
        raise RuntimeError("YABAI_REQUIRE_LIVE=1 but no graph/auth credentials were present")

    record.update({"ok": True, "duration_s": _now() - started, "results": results})
    _checkpoint(client, job_id, "complete", "ok", {"duration_s": record["duration_s"], "mode": record["mode"]})
    _append_marker(marker_path, record)
    return record


async def _worker_loop(stop_event: asyncio.Event, wake_event: asyncio.Event, client: KotobaDatomicClient) -> None:
    while not stop_event.is_set():
        jobs = await asyncio.to_thread(_ready_jobs, client)
        if not jobs:
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
            wake_event.clear()
            continue

        job = jobs[0]
        job_id = str(job["id"])
        payload = json.loads(job.get("payload_json") or "{}")
        attempts = int(job.get("attempts") or 0) + 1
        try:
            await asyncio.to_thread(_set_job_status, client, job_id, "running", attempts=attempts)
            result = await _run_pipeline(job_id, payload, client)
            status = "done" if result.get("ok") else "failed"
            await asyncio.to_thread(
                _set_job_status,
                client,
                job_id,
                status,
                last_error=None if result.get("ok") else json.dumps(result, ensure_ascii=False, default=str),
            )
        except Exception as caught:
            max_attempts = int(job.get("max_attempts") or 5)
            status = "failed" if attempts >= max_attempts else "pending"
            await asyncio.to_thread(_checkpoint, client, job_id, "error", status, {"error": str(caught)})
            await asyncio.to_thread(_set_job_status, client, job_id, status, attempts=attempts, last_error=str(caught))


async def serve(stop_event: asyncio.Event, healthz_port: int, api_port: int) -> None:
    """Run Yabai as a Kotoba Datomic-backed queue worker."""
    from aiohttp import web

    client = _client()
    wake_event = asyncio.Event()

    try:
        if _load_job(client, "yabai-boot") is None:
            enqueue_job(kind="persist", payload={"source": "boot"}, priority=50, job_id="yabai-boot", client=client)
    except KotobaTransactError as caught:
        raise RuntimeError(f"Kotoba Datomic queue unavailable: {caught}") from caught

    async def healthz(_request: web.Request) -> web.Response:
        try:
            counts = await asyncio.to_thread(_job_counts, client)
            return web.json_response({
                "ok": True,
                "service": CELL_NAME,
                "actor_did": ACTOR_DID,
                "queue": counts,
                "graph": QUEUE_GRAPH,
                "store": "kotoba-datomic",
            })
        except Exception as caught:
            return web.json_response({"ok": False, "error": str(caught), "store": "kotoba-datomic"}, status=503)

    async def jobs(request: web.Request) -> web.Response:
        limit = int(request.query.get("limit", "20"))
        rows = await asyncio.to_thread(_latest_jobs, client, max(1, min(limit, 100)))
        return web.json_response({"jobs": rows, "graph": QUEUE_GRAPH})

    async def enqueue(request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else {}
        try:
            jid = await asyncio.to_thread(
                enqueue_job,
                kind=str(body.get("kind") or "persist"),
                payload=body.get("payload") if isinstance(body.get("payload"), dict) else {},
                priority=int(body.get("priority") or 100),
                client=client,
            )
        except Exception as caught:
            return web.json_response({"ok": False, "error": str(caught)}, status=503)
        wake_event.set()
        return web.json_response({"ok": True, "job_id": jid, "graph": QUEUE_GRAPH}, status=202)

    app = web.Application()
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/jobs", jobs)
    app.router.add_post("/enqueue", enqueue)

    bind = os.environ.get("YABAI_BIND", "127.0.0.1")
    runner = web.AppRunner(app)
    await runner.setup()
    sites = [web.TCPSite(runner, bind, api_port)]
    if healthz_port != api_port:
        sites.append(web.TCPSite(runner, bind, healthz_port))
    for site in sites:
        await site.start()

    worker = asyncio.create_task(_worker_loop(stop_event, wake_event, client))
    wake_event.set()
    try:
        await stop_event.wait()
    finally:
        worker.cancel()
        await runner.cleanup()
        try:
            await worker
        except asyncio.CancelledError:
            pass


async def yabai_tor_torrent_persistence_cell() -> dict[str, Any]:
    client = _client()
    job_id = enqueue_job(kind="persist", payload={"source": "manual-one-shot"}, priority=10, client=client)
    result = await _run_pipeline(job_id, {"source": "manual-one-shot"}, client)
    await asyncio.to_thread(_set_job_status, client, job_id, "done" if result.get("ok") else "failed")
    return result

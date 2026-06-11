"""Murakumo cell for the yabai Tor/Torrent CTI persistence path.

The cell runs as a LAN API worker with a local durable SQLite queue. Jobs are
processed immediately when enqueued, each step is checkpointed, and the legacy
one-shot entry remains available for manual repair.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from typing import Any

ACTOR_DID = "did:web:etzhayyim.com:actor:yabai"
CELL_NAME = "YabaiTorTorrentCtiPersistenceCell"
STALE_LEASE_S = 600


def _repo_root() -> pathlib.Path:
    configured = os.environ.get("ETZHAYYIM_ROOT") or os.environ.get("ETZ_REPO")
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


def _db_path(repo: pathlib.Path) -> pathlib.Path:
    return _state_dir(repo) / "cti-correlator-queue.sqlite3"


def _connect(db_path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            next_run_at INTEGER NOT NULL,
            leased_until INTEGER,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            last_error TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
            job_id TEXT NOT NULL,
            step TEXT NOT NULL,
            status TEXT NOT NULL,
            ts INTEGER NOT NULL,
            detail_json TEXT NOT NULL,
            PRIMARY KEY (job_id, step, ts)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(status, next_run_at, priority)")
    conn.commit()
    return conn


def _checkpoint(conn: sqlite3.Connection, job_id: str, step: str, status: str, detail: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO checkpoints(job_id, step, status, ts, detail_json) VALUES (?, ?, ?, ?, ?)",
        (job_id, step, status, time.time_ns(), json.dumps(detail, ensure_ascii=False, sort_keys=True)),
    )
    conn.commit()


def enqueue_job(
    *,
    kind: str = "persist",
    payload: dict[str, Any] | None = None,
    priority: int = 100,
    job_id: str | None = None,
) -> str:
    repo = _repo_root()
    now = int(time.time())
    jid = job_id or f"yabai-{now}-{uuid.uuid4().hex[:12]}"
    with _connect(_db_path(repo)) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs(
                id, kind, payload_json, status, priority, attempts, max_attempts,
                next_run_at, leased_until, created_at, updated_at, last_error
            ) VALUES (?, ?, ?, 'pending', ?, 0, 5, ?, NULL, ?, ?, NULL)
            """,
            (jid, kind, json.dumps(payload or {}, ensure_ascii=False, sort_keys=True), priority, now, now, now),
        )
        conn.commit()
    return jid


def _lease_next(conn: sqlite3.Connection) -> sqlite3.Row | None:
    now = int(time.time())
    conn.execute(
        """
        UPDATE jobs
        SET status='pending', leased_until=NULL, updated_at=?
        WHERE status='running' AND leased_until IS NOT NULL AND leased_until < ?
        """,
        (now, now),
    )
    row = conn.execute(
        """
        SELECT * FROM jobs
        WHERE status='pending' AND next_run_at <= ?
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
        """,
        (now,),
    ).fetchone()
    if row is None:
        conn.commit()
        return None
    conn.execute(
        """
        UPDATE jobs
        SET status='running', attempts=attempts + 1, leased_until=?, updated_at=?
        WHERE id=? AND status='pending'
        """,
        (now + STALE_LEASE_S, now, row["id"]),
    )
    conn.commit()
    return conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()


def _job_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
    return {str(row["status"]): int(row["n"]) for row in rows}


def _latest_jobs(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, kind, status, attempts, created_at, updated_at, last_error
        FROM jobs
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


async def _run_pipeline(job_id: str, payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    _guardrails()
    repo = _repo_root()
    actor = repo / "20-actors" / "yabai"
    methods = actor / "methods"
    state = _state_dir(repo)
    marker_path = state / "cti-correlator-runs.ndjson"

    env = os.environ.copy()
    env.setdefault("KOTOBA_AUDIT_STRICT", "1")
    env.setdefault("PYTHONUTF8", "1")

    started = int(time.time())
    record: dict[str, Any] = {
        "ts": started,
        "job_id": job_id,
        "cell": CELL_NAME,
        "actor_did": ACTOR_DID,
        "node": os.environ.get("ETZHAYYIM_NODE_NAME") or os.environ.get("ETZHAYYIM_NODE"),
        "mode": "live" if (env.get("YABAI_GRAPH_CID") and (env.get("KOTOBA_TOKEN") or env.get("KOTOBA_CACAO_B64"))) else "dry-run",
        "payload": payload,
        "boundary": "public Tor-exit indicators + case-bound BitTorrent evidence only; no de-anonymization",
    }

    steps = [
        ("ingest", [sys.executable, str(methods / "ingest.py")]),
        ("analyze", [sys.executable, str(methods / "analyze.py")]),
        ("transact", [sys.executable, str(methods / "transact.py")]),
    ]
    results = []
    for step_name, step_cmd in steps:
        _checkpoint(conn, job_id, step_name, "started", {"cmd": step_cmd})
        result = await _run(step_cmd, actor, env)
        results.append(result)
        _checkpoint(conn, job_id, step_name, "ok" if result["returncode"] == 0 else "failed", result)
        if result["returncode"] != 0:
            record.update({"ok": False, "failed_step": step_name, "results": results})
            _append_marker(marker_path, record)
            return record

    if record["mode"] != "live" and env.get("YABAI_REQUIRE_LIVE") == "1":
        record.update({"ok": False, "failed_step": "transact", "results": results, "error": "live credentials missing"})
        _append_marker(marker_path, record)
        raise RuntimeError("YABAI_REQUIRE_LIVE=1 but no graph/auth credentials were present")

    record.update({"ok": True, "duration_s": int(time.time()) - started, "results": results})
    _checkpoint(conn, job_id, "complete", "ok", {"duration_s": record["duration_s"], "mode": record["mode"]})
    _append_marker(marker_path, record)
    return record


async def _worker_loop(stop_event: asyncio.Event, wake_event: asyncio.Event, db_path: pathlib.Path) -> None:
    with _connect(db_path) as conn:
        while not stop_event.is_set():
            job = _lease_next(conn)
            if job is None:
                try:
                    await asyncio.wait_for(wake_event.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass
                wake_event.clear()
                continue

            job_id = str(job["id"])
            payload = json.loads(job["payload_json"] or "{}")
            try:
                result = await _run_pipeline(job_id, payload, conn)
                status = "done" if result.get("ok") else "failed"
                conn.execute(
                    "UPDATE jobs SET status=?, leased_until=NULL, updated_at=?, last_error=? WHERE id=?",
                    (status, int(time.time()), None if result.get("ok") else json.dumps(result, ensure_ascii=False), job_id),
                )
            except Exception as caught:
                now = int(time.time())
                retry_at = now + min(3600, 60 * int(job["attempts"] or 1))
                status = "failed" if int(job["attempts"]) >= int(job["max_attempts"]) else "pending"
                conn.execute(
                    "UPDATE jobs SET status=?, leased_until=NULL, next_run_at=?, updated_at=?, last_error=? WHERE id=?",
                    (status, retry_at, now, str(caught), job_id),
                )
                _checkpoint(conn, job_id, "error", status, {"error": str(caught)})
            conn.commit()


async def serve(stop_event: asyncio.Event, healthz_port: int, api_port: int) -> None:
    """Run Yabai as a durable queue worker.

    Endpoints:
      GET  /healthz
      GET  /jobs
      POST /enqueue {"kind":"persist","payload":{...},"priority":100}
    """
    from aiohttp import web

    repo = _repo_root()
    db_path = _db_path(repo)
    wake_event = asyncio.Event()

    with _connect(db_path) as conn:
        pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('pending', 'running')").fetchone()[0]
        if int(pending) == 0:
            enqueue_job(kind="persist", payload={"source": "boot"}, priority=50, job_id="yabai-boot")

    async def healthz(_request: web.Request) -> web.Response:
        with _connect(db_path) as conn:
            return web.json_response({
                "ok": True,
                "service": CELL_NAME,
                "actor_did": ACTOR_DID,
                "queue": _job_counts(conn),
                "db_path": str(db_path),
            })

    async def jobs(request: web.Request) -> web.Response:
        limit = int(request.query.get("limit", "20"))
        with _connect(db_path) as conn:
            return web.json_response({"jobs": _latest_jobs(conn, max(1, min(limit, 100)))})

    async def enqueue(request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else {}
        jid = enqueue_job(
            kind=str(body.get("kind") or "persist"),
            payload=body.get("payload") if isinstance(body.get("payload"), dict) else {},
            priority=int(body.get("priority") or 100),
        )
        wake_event.set()
        return web.json_response({"ok": True, "job_id": jid}, status=202)

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

    worker = asyncio.create_task(_worker_loop(stop_event, wake_event, db_path))
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
    repo = _repo_root()
    db_path = _db_path(repo)
    job_id = enqueue_job(kind="persist", payload={"source": "manual-one-shot"}, priority=10)
    with _connect(db_path) as conn:
        result = await _run_pipeline(job_id, {"source": "manual-one-shot"}, conn)
        conn.execute(
            "UPDATE jobs SET status=?, leased_until=NULL, updated_at=?, last_error=? WHERE id=?",
            ("done" if result.get("ok") else "failed", int(time.time()), None if result.get("ok") else json.dumps(result), job_id),
        )
        conn.commit()
    return result

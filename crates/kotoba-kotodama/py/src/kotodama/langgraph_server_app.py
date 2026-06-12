"""
LangGraph Server — FastAPI + Granian ASGI entry point (ADR-2605080600 Phase 2).

Architecture:
  CF Worker → bpmn-dispatcher → POST /runs → this app → RisingWave

/runs API (LangGraph Server compatible surface):
  POST /runs              — submit background graph run (returns run_id)
  GET  /runs/{run_id}     — poll run status + output
  POST /threads           — create a new stateful actor thread
  GET  /threads/{tid}/state — latest checkpoint state for a thread
  GET  /assistants        — list registered graphs
  GET  /healthz           — liveness
  GET  /readyz            — readiness (DB reachable)

Execution model:
  - POST /runs → in-memory _RUNS dict (status=pending) + RisingWave row
  - FastAPI BackgroundTask executes graph with kotoba checkpoint saver (RisingWave fallback via KOTODAMA_LG_BACKEND=rw)
  - Output written back to _RUNS + RisingWave (status=success|error)
  - Redis BLPOP queue added in Phase 3 for multi-pod dispatch

Startup via Granian:
  granian --interface asgi --host 0.0.0.0 --port 8000 \\
          kotodama.langgraph_server_app:app
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from kotodama.rw_async_pool import ensure_rw_async_pool

LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory run store (primary; RW is durable backing)
# ---------------------------------------------------------------------------

_RUNS: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Graph registry: assistant_id → compiled StateGraph
# ---------------------------------------------------------------------------

_GRAPH_REGISTRY: dict[str, Any] = {}


_SKIP_IF_EXISTS = (
    False  # phase 2 toggle: when True, register_graph is no-op for ids already present
)


def register_graph(assistant_id: str, graph: Any) -> None:
    """Register a compiled LangGraph StateGraph under an assistant_id.

    Honors module-level ``_SKIP_IF_EXISTS`` flag (set during static-fallback
    pass after the DB-row registration has run, so that static block fills
    gaps only and DB rows take precedence).
    """
    if _SKIP_IF_EXISTS and assistant_id in _GRAPH_REGISTRY:
        return
    _GRAPH_REGISTRY[assistant_id] = graph
    LOG.info("Registered graph assistant_id=%s", assistant_id)


async def _rw_audit_event(
    run_id: str,
    assistant_id: str,
    thread_id: str,
    actor_did: str,
    from_status: str | None,
    to_status: str,
    error_message: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Append a lifecycle event to py_audit_langgraph_event (best-effort, non-fatal)."""
    try:
        pool = await ensure_rw_async_pool()
        event_id = str(uuid.uuid4())
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO py_audit_langgraph_event
                  (event_id, run_id, assistant_id, thread_id, actor_did,
                   from_status, to_status, error_message, latency_ms, ts_ms)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    event_id,
                    run_id,
                    assistant_id,
                    thread_id,
                    actor_did,
                    from_status,
                    to_status,
                    error_message,
                    latency_ms,
                    _now_ms(),
                ),
            )
    except Exception as e:
        LOG.debug("audit_event skipped (non-fatal): %s", e)


async def _rw_upsert_run(row: dict) -> None:
    """Delete-then-insert pattern (RisingWave has no ON CONFLICT UPDATE)."""
    try:
        pool = await ensure_rw_async_pool()
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM vertex_langgraph_run WHERE vertex_id = %s",
                (row["vertex_id"],),
            )
            await conn.execute(
                """
                INSERT INTO vertex_langgraph_run
                  (vertex_id, actor_did, thread_id, checkpoint_ns, assistant_id,
                   status, input_json, output_json, error_message,
                   started_at, completed_at, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row["vertex_id"],
                    row.get("actor_did", ""),
                    row.get("thread_id", ""),
                    row.get("checkpoint_ns", ""),
                    row.get("assistant_id", ""),
                    row.get("status", "pending"),
                    row.get("input_json"),
                    row.get("output_json"),
                    row.get("error_message"),
                    row.get("started_at"),
                    row.get("completed_at"),
                    row.get("created_at", _now_ms()),
                ),
            )
    except Exception as e:
        LOG.warning("RW upsert_run skipped (non-fatal): %s", e)


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Graph execution worker
# ---------------------------------------------------------------------------


async def _execute_graph(run_id: str, assistant_id: str, thread_id: str, input_data: dict) -> None:
    """Execute a graph in the background, updating run status in _RUNS + RisingWave."""
    run = _RUNS.get(run_id)
    if run is None:
        LOG.warning("run_id=%s not found in _RUNS", run_id)
        return

    actor_did = run.get("actor_did", "")
    run["status"] = "running"
    run["started_at"] = _now_ms()
    await _rw_upsert_run(run)
    await _rw_audit_event(run_id, assistant_id, thread_id, actor_did, "pending", "running")

    try:
        graph = _GRAPH_REGISTRY.get(assistant_id)
        if graph is None:
            raise ValueError(f"Unknown assistant_id: {assistant_id!r}")

        config: dict = {"configurable": {"thread_id": thread_id}}

        try:
            if os.environ.get("KOTODAMA_LG_BACKEND", "kotoba") != "rw":
                from kotodama.langgraph_checkpoint_kotoba import get_checkpoint_saver
            else:
                from kotodama.langgraph_checkpoint_rw import get_checkpoint_saver

            saver = await get_checkpoint_saver()
            config["checkpointer"] = saver
        except Exception as e:
            LOG.debug("Checkpoint saver unavailable (running stateless): %s", e)

        result = await graph.ainvoke(input_data, config)
        output_json = json.dumps(result, ensure_ascii=False, default=str)

        completed_at = _now_ms()
        latency_ms = completed_at - run["started_at"] if run.get("started_at") else None
        run["status"] = "success"
        run["output_json"] = output_json
        run["completed_at"] = completed_at
        LOG.info("run_id=%s assistant=%s completed OK", run_id, assistant_id)
        await _rw_audit_event(
            run_id,
            assistant_id,
            thread_id,
            actor_did,
            "running",
            "success",
            latency_ms=latency_ms,
        )

    except Exception as exc:
        LOG.exception("run_id=%s failed: %s", run_id, exc)
        completed_at = _now_ms()
        latency_ms = completed_at - run["started_at"] if run.get("started_at") else None
        run["status"] = "error"
        run["error_message"] = str(exc)
        run["completed_at"] = completed_at
        await _rw_audit_event(
            run_id,
            assistant_id,
            thread_id,
            actor_did,
            "running",
            "error",
            error_message=str(exc),
            latency_ms=latency_ms,
        )

    await _rw_upsert_run(run)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    assistant_id: str
    thread_id: str | None = None
    actor_did: str | None = None
    input: dict = {}
    config: dict = {}


class ThreadRequest(BaseModel):
    assistant_id: str
    actor_did: str | None = None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(application: FastAPI):
    LOG.info("LangGraph Server starting up (ADR-2605080600 Phase 2)")
    # Phase 2 (DB-first / static-fallback): try DB rows first; static block
    # then runs with _SKIP_IF_EXISTS so it only fills gaps. If DB is down,
    # the static block registers everything as before. The static block is
    # removed in a follow-up commit once one Cron firing has been observed
    # exercising a DB-row-driven assistant.
    db_loaded = 0
    initial_seen: dict[str, tuple] = {}
    try:
        await ensure_rw_async_pool()
        LOG.info("DB pool ready")
        await _reconcile_orphan_runs()
        try:
            from kotodama.langgraph_loader import load_active_graphs

            result = await load_active_graphs(
                pool_factory=ensure_rw_async_pool,
                register_fn=register_graph,
            )
            db_loaded = result.get("loaded", 0)
            initial_seen = result.get("seen", {}) or {}
            LOG.info("DB-driven assistants registered: %d (seen=%d)", db_loaded, len(initial_seen))
        except Exception as e:
            LOG.warning("load_active_graphs failed (non-fatal): %s", e)
    except Exception as e:
        LOG.warning("DB pool not available at startup: %s", e)

    # Static fallback fills any gaps (or registers everything when DB was down).
    pre_static = len(_GRAPH_REGISTRY)
    global _SKIP_IF_EXISTS
    _SKIP_IF_EXISTS = True
    try:
        _register_builtin_graphs()
    finally:
        _SKIP_IF_EXISTS = False
    static_filled = len(_GRAPH_REGISTRY) - pre_static
    _LIFESPAN_STATS["db_loaded"] = db_loaded
    _LIFESPAN_STATS["static_filled"] = static_filled
    LOG.info(
        "Total assistants in registry: %d (db=%d, static_filled=%d)",
        len(_GRAPH_REGISTRY),
        db_loaded,
        static_filled,
    )

    # Phase-4 hot-reload watcher. Polls vertex_langgraph_deployment every
    # LANGGRAPH_RELOAD_INTERVAL_SEC (default 30s) for diffs and reconciles
    # _GRAPH_REGISTRY without pod restart. Disabled by setting the env
    # variable to 0 or negative.
    watcher_task = None
    try:
        from kotodama.langgraph_watcher import watch_forever
        import os as _os

        interval = float(_os.environ.get("LANGGRAPH_RELOAD_INTERVAL_SEC", "30"))
        if interval > 0:

            def _pop(aid: str) -> None:
                _GRAPH_REGISTRY.pop(aid, None)

            watcher_task = asyncio.create_task(
                watch_forever(
                    pool_factory=ensure_rw_async_pool,
                    register_fn=register_graph,
                    pop_fn=_pop,
                    interval_sec=interval,
                    initial_seen=initial_seen,
                )
            )
            LOG.info("Hot-reload watcher started (interval=%.1fs)", interval)
        else:
            LOG.info("Hot-reload watcher disabled (LANGGRAPH_RELOAD_INTERVAL_SEC<=0)")
    except Exception as e:
        LOG.warning("Could not start hot-reload watcher: %s", e)

    try:
        yield
    finally:
        if watcher_task is not None:
            watcher_task.cancel()
            try:
                await watcher_task
            except (asyncio.CancelledError, Exception):
                pass


async def _reconcile_orphan_runs() -> None:
    """On startup, drop stale `running` rows in vertex_langgraph_run.

    A pod restart mid-execution leaves rows in status='running' forever
    (the final _rw_upsert_run never lands). Dropping rows older than
    30min keeps dashboards free of false in-flight work. We delete
    rather than transition to 'error' because RisingWave lacks an
    UPDATE-by-WHERE that's safe under our DDL guard, and the audit
    trail is preserved in py_audit_langgraph_event regardless.
    """
    try:
        pool = await ensure_rw_async_pool()
        cutoff_ms = _now_ms() - (30 * 60 * 1000)
        async with pool.connection() as conn:
            cur = await conn.execute(
                "SELECT vertex_id FROM vertex_langgraph_run "
                "WHERE status = 'running' AND started_at < %s",
                (cutoff_ms,),
            )
            stale = [row[0] for row in await cur.fetchall()]
            for vid in stale:
                await conn.execute(
                    "DELETE FROM vertex_langgraph_run WHERE vertex_id = %s",
                    (vid,),
                )
            if stale:
                LOG.info("reconcile_orphan_runs: dropped %d stale running rows", len(stale))
    except Exception as e:
        LOG.warning("reconcile_orphan_runs skipped (non-fatal): %s", e)


app = FastAPI(
    title="etzhayyim LangGraph Server",
    version="2.0.0",
    description="L3 Virtual Actor Runtime — ADR-2605080600",
    lifespan=_lifespan,
)

# ---------------------------------------------------------------------------
# XRPC façade routers (one per NSID family).
#
# Mounted here so that every actor's procedures/queries are served from the
# same FastAPI app and reachable through the unified etzhayyim.com/xrpc/
# gateway (CF Worker at 50-infra/etzhayyim-did-web). No per-actor subdomain.
# ---------------------------------------------------------------------------
from kotodama.xrpc.unispsc import router as _unispsc_xrpc_router  # noqa: E402

app.include_router(_unispsc_xrpc_router)


# ---------------------------------------------------------------------------
# /runs API
# ---------------------------------------------------------------------------


@app.post("/runs", status_code=202)
async def create_run(body: RunRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    thread_id = body.thread_id or str(uuid.uuid4())
    actor_did = body.actor_did or f"did:web:{body.assistant_id}.etzhayyim.com"

    if body.assistant_id not in _GRAPH_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"assistant_id not found: {body.assistant_id!r}. "
            f"Available: {list(_GRAPH_REGISTRY)}",
        )

    now = _now_ms()
    run: dict = {
        "vertex_id": run_id,
        "actor_did": actor_did,
        "thread_id": thread_id,
        "checkpoint_ns": "",
        "assistant_id": body.assistant_id,
        "status": "pending",
        "input_json": json.dumps(body.input, ensure_ascii=False),
        "output_json": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
    }
    _RUNS[run_id] = run

    background_tasks.add_task(_rw_upsert_run, run.copy())
    background_tasks.add_task(
        _execute_graph,
        run_id=run_id,
        assistant_id=body.assistant_id,
        thread_id=thread_id,
        input_data=body.input,
    )

    return {"run_id": run_id, "thread_id": thread_id, "status": "pending"}


@app.post("/runs/stream")
async def create_run_stream(body: RunRequest, request: Request):
    """SSE-streamed graph execution.

    Pregel super-step events streamed as Server-Sent Events. Each `data:`
    line is one JSON event. Two channels are interleaved:
      - LangGraph runtime events from `astream_events(v2)`
        (on_chain_start / on_chain_end / on_chat_model_stream / ...)
      - A final `event: run` line carrying the terminal state

    Client disconnect is detected via `request.is_disconnected()` and
    aborts the stream cleanly.
    """
    run_id = str(uuid.uuid4())
    thread_id = body.thread_id or str(uuid.uuid4())
    actor_did = body.actor_did or f"did:web:{body.assistant_id}.etzhayyim.com"

    graph = _GRAPH_REGISTRY.get(body.assistant_id)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=f"assistant_id not found: {body.assistant_id!r}",
        )

    started_at = _now_ms()
    run: dict = {
        "vertex_id": run_id,
        "actor_did": actor_did,
        "thread_id": thread_id,
        "checkpoint_ns": "",
        "assistant_id": body.assistant_id,
        "status": "running",
        "input_json": json.dumps(body.input, ensure_ascii=False),
        "output_json": None,
        "error_message": None,
        "started_at": started_at,
        "completed_at": None,
        "created_at": started_at,
    }
    _RUNS[run_id] = run
    await _rw_upsert_run(run.copy())

    async def _sse_iter():
        # Initial run handshake — clients can immediately render thread/run ids.
        yield (
            "event: run\n"
            f"data: {json.dumps({'run_id': run_id, 'thread_id': thread_id, 'status': 'running'})}\n\n"
        ).encode("utf-8")

        try:
            saver = None
            try:
                if os.environ.get("KOTODAMA_LG_BACKEND", "kotoba") != "rw":
                    from kotodama.langgraph_checkpoint_kotoba import get_checkpoint_saver
                else:
                    from kotodama.langgraph_checkpoint_rw import get_checkpoint_saver

                saver = await get_checkpoint_saver()
            except Exception as e:  # pragma: no cover — checkpointer is optional
                LOG.debug("stream: checkpointer unavailable: %s", e)

            config: dict[str, Any] = {
                "configurable": {"thread_id": thread_id, "checkpoint_ns": ""},
                "run_id": run_id,
            }
            target = graph
            if saver is not None and hasattr(graph, "with_config"):
                try:
                    target = graph.with_config({"checkpointer": saver})
                except Exception:
                    target = graph

            final_state: Any = None
            astream_events = getattr(target, "astream_events", None)
            if astream_events is None:
                # Fallback: emit a single chunk via ainvoke if streaming unavailable.
                final_state = await target.ainvoke(body.input, config=config)
                yield (
                    "event: chunk\n"
                    f"data: {json.dumps({'kind': 'final', 'state': _json_safe(final_state)})}\n\n"
                ).encode("utf-8")
            else:
                async for ev in astream_events(body.input, config=config, version="v2"):
                    if await request.is_disconnected():
                        LOG.info("stream: client disconnected run_id=%s", run_id)
                        break
                    payload = {
                        "event": ev.get("event"),
                        "name": ev.get("name"),
                        "tags": ev.get("tags") or [],
                        "data": _json_safe(ev.get("data")),
                    }
                    yield (
                        f"event: chunk\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    ).encode("utf-8")
                    if ev.get("event") == "on_chain_end" and ev.get("name") in (
                        "LangGraph",
                        "__end__",
                    ):
                        final_state = ev.get("data", {}).get("output")

            completed = _now_ms()
            run["status"] = "success"
            run["output_json"] = json.dumps(_json_safe(final_state), ensure_ascii=False)
            run["completed_at"] = completed
            await _rw_upsert_run(run.copy())
            yield (
                "event: run\n"
                f"data: {json.dumps({'run_id': run_id, 'status': 'success', 'completed_at': completed})}\n\n"
            ).encode("utf-8")
        except Exception as exc:
            LOG.exception("stream: run failed run_id=%s", run_id)
            run["status"] = "error"
            run["error_message"] = str(exc)
            run["completed_at"] = _now_ms()
            await _rw_upsert_run(run.copy())
            yield (
                f"event: error\ndata: {json.dumps({'run_id': run_id, 'error': str(exc)})}\n\n"
            ).encode("utf-8")

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
        "Connection": "keep-alive",
    }
    return StreamingResponse(_sse_iter(), media_type="text/event-stream", headers=headers)


def _json_safe(obj: Any) -> Any:
    """Best-effort JSON sanitization for streamed event payloads."""
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        if isinstance(obj, dict):
            return {str(k): _json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_json_safe(v) for v in obj]
        return str(obj)


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = _RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return {
        "run_id": run["vertex_id"],
        "status": run["status"],
        "assistant_id": run["assistant_id"],
        "thread_id": run["thread_id"],
        "output": json.loads(run["output_json"]) if run.get("output_json") else None,
        "error": run.get("error_message"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "created_at": run["created_at"],
    }


# ---------------------------------------------------------------------------
# /threads API
# ---------------------------------------------------------------------------


@app.post("/threads", status_code=201)
async def create_thread(body: ThreadRequest):
    thread_id = str(uuid.uuid4())
    return {"thread_id": thread_id, "assistant_id": body.assistant_id, "created_at": _now_ms()}


@app.get("/threads/{thread_id}/state")
async def get_thread_state(thread_id: str):
    """Return the latest checkpoint state for a thread."""
    try:
        if os.environ.get("KOTODAMA_LG_BACKEND", "kotoba") != "rw":
            from kotodama.langgraph_checkpoint_kotoba import get_checkpoint_saver
        else:
            from kotodama.langgraph_checkpoint_rw import get_checkpoint_saver

        saver = await get_checkpoint_saver()
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint_tuple = await saver.aget_tuple(config)
        if checkpoint_tuple is None:
            return {"thread_id": thread_id, "state": None}
        return {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_tuple.config.get("configurable", {}).get("checkpoint_id"),
            "state": checkpoint_tuple.checkpoint.get("channel_values", {}),
        }
    except Exception as e:
        LOG.warning("Could not read thread state: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# /assistants API
# ---------------------------------------------------------------------------


@app.get("/assistants")
async def list_assistants():
    return [
        {"assistant_id": aid, "graph_type": type(g).__name__} for aid, g in _GRAPH_REGISTRY.items()
    ]


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "langgraph-server", "version": "2.0.0"}


_LIFESPAN_STATS: dict[str, int] = {"db_loaded": 0, "static_filled": 0}


@app.get("/registry-source")
async def registry_source():
    """Diagnostic for rollout phases — composition of _GRAPH_REGISTRY."""
    try:
        from kotodama.langgraph_watcher import STATS as _watcher_stats

        watcher = _watcher_stats.to_dict()
    except Exception:
        watcher = {"running": False}
    return {
        "total": len(_GRAPH_REGISTRY),
        "db_loaded": _LIFESPAN_STATS.get("db_loaded", 0),
        "static_filled": _LIFESPAN_STATS.get("static_filled", 0),
        "watcher": watcher,
    }


@app.get("/readyz")
async def readyz():
    timeout_s = float(os.environ.get("LANGGRAPH_READYZ_DB_TIMEOUT_S", "2.0"))

    async def _probe() -> None:
        import psycopg

        dsn = os.environ.get("RW_URL") or os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("RW_URL (or DATABASE_URL) not set")
        conn = await psycopg.AsyncConnection.connect(
            dsn,
            autocommit=True,
            prepare_threshold=0,
            connect_timeout=timeout_s,
        )
        try:
            await asyncio.wait_for(conn.execute("SELECT 1"), timeout=timeout_s)
        finally:
            await conn.close()

    try:
        await asyncio.wait_for(_probe(), timeout=timeout_s)
        return {"ok": True, "db": "connected", "graphs": len(_GRAPH_REGISTRY)}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "db": "unreachable", "error": str(e)},
        )


# ---------------------------------------------------------------------------
# Builtin graphs
# ---------------------------------------------------------------------------


def _register_builtin_graphs() -> None:
    """Phase-3 (2026-05-08): static registration disabled.

    All 63 builtin assistants now live as ``vertex_langgraph_assistant`` rows
    seeded by alembic ``r_20260509120000_seed_langgraph_builtin_63`` and
    loaded via ``langgraph_loader.load_active_graphs`` at startup.

    The function is preserved as a no-op so the lifespan call site stays
    intact; if RW is unavailable at boot, ``/registry-source`` will report
    ``db_loaded=0, static_filled=0`` and the operator can roll back to v3
    (which still had the static fallback) by re-pinning the prior image.

    Per-graph helper functions ``_register_*`` below are retained for tests
    that import them directly.
    """
    # Transitional gap-fill for the 2026-05-15 ransomware actor rollout.
    # The DB registry row is seeded by
    # 20260515112000_ransomware_actor_activity_langgraph, but this keeps the
    # deployed CronJob runnable while RisingWave is recovering or before the
    # migration has propagated. _SKIP_IF_EXISTS prevents duplicate registration.
    try:
        _register_ransomware_actor_activity()
    except Exception as e:
        LOG.warning("Could not register ransomware_actor_activity graph: %s", e)
    return
    # ---- legacy static registration (disabled, kept for revert reference) ----
    try:
        _register_pregel_email_triage()
    except Exception as e:
        LOG.warning("Could not register pregel-email-triage graph: %s", e)
    try:
        _register_echo_graph()
    except Exception as e:
        LOG.warning("Could not register builtin graphs: %s", e)
    try:
        _register_shosha_agent_loop()
    except Exception as e:
        LOG.warning("Could not register shosha_agent_loop graph: %s", e)
    try:
        _register_shosha_market_intelligence()
    except Exception as e:
        LOG.warning("Could not register shosha_market_intelligence graph: %s", e)
    try:
        _register_shosha_trade_book_recompute()
    except Exception as e:
        LOG.warning("Could not register shosha_trade_book_recompute graph: %s", e)
    try:
        _register_shosha_react_upstream()
    except Exception as e:
        LOG.warning("Could not register shosha_react_upstream graph: %s", e)
    try:
        _register_webmk_proposal()
    except Exception as e:
        LOG.warning("Could not register webmk_create_proposal graph: %s", e)
    try:
        _register_ki_synthesis()
    except Exception as e:
        LOG.warning("Could not register ki.synthesize.v1 graph: %s", e)
    try:
        _register_ki_cycle()
    except Exception as e:
        LOG.warning("Could not register ki.cycle.v1 graph: %s", e)
    try:
        _register_saikin_cycle()
    except Exception as e:
        LOG.warning("Could not register saikin.cycle.v1 graph: %s", e)
    try:
        _register_newsletter_send_campaign()
    except Exception as e:
        LOG.warning("Could not register newsletter_send_campaign graph: %s", e)
    try:
        _register_organism_single_task_chains()
    except Exception as e:
        LOG.warning("Could not register organism single-task chains: %s", e)
    try:
        _register_koke_cycle()
    except Exception as e:
        LOG.warning("Could not register koke.cycle.v1 graph: %s", e)
    try:
        _register_shosha_trade_idea_synthesize()
    except Exception as e:
        LOG.warning("Could not register shosha_trade_idea_synthesize graph: %s", e)
    try:
        _register_shosha_daily_report()
    except Exception as e:
        LOG.warning("Could not register shosha_daily_report graph: %s", e)
    try:
        _register_shinshi_seed_gap_fill()
    except Exception as e:
        LOG.warning("Could not register shinshi_seed_gap_fill graph: %s", e)
    try:
        _register_yoro_platform_pulse()
    except Exception as e:
        LOG.warning("Could not register yoro_platform_pulse graph: %s", e)
    try:
        _register_copyright_ingest()
    except Exception as e:
        LOG.warning("Could not register copyright_ingest graph: %s", e)
    try:
        _register_yoro_product_ingest()
    except Exception as e:
        LOG.warning("Could not register yoro_product_ingest graph: %s", e)
    try:
        _register_copyright_fulltext()
    except Exception as e:
        LOG.warning("Could not register copyright_fulltext graph: %s", e)
    try:
        _register_animeka_autopilot()
    except Exception as e:
        LOG.warning("Could not register animeka_autopilot graph: %s", e)
    try:
        _register_shinka_cron_tick()
    except Exception as e:
        LOG.warning("Could not register shinka_cron_tick graph: %s", e)
    try:
        _register_wellbecoming_process_mining()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_process_mining graph: %s", e)
    try:
        _register_wellbecoming_detect_bottleneck()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_detect_bottleneck graph: %s", e)
    try:
        _register_wellbecoming_proactive_connect()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_proactive_connect graph: %s", e)
    try:
        _register_wellbecoming_floor_violation_alert()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_floor_violation_alert graph: %s", e)
    try:
        _register_wellbecoming_minimax_sweep()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_minimax_sweep graph: %s", e)
    try:
        _register_wellbecoming_belief_influence_propagate()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_belief_influence_propagate graph: %s", e)
    try:
        _register_wellbecoming_belief_noise_inject()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_belief_noise_inject graph: %s", e)
    try:
        _register_wellbecoming_belief_restoring_capture()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_belief_restoring_capture graph: %s", e)
    try:
        _register_wellbecoming_trust_weight_update()
    except Exception as e:
        LOG.warning("Could not register wellbecoming_trust_weight_update graph: %s", e)
    try:
        _register_etzhayyim_company_ops()
    except Exception as e:
        LOG.warning("Could not register etzhayyim_company_ops graph: %s", e)
    try:
        _register_lawfirm_marketing_ops()
    except Exception as e:
        LOG.warning("Could not register lawfirm_marketing_ops graph: %s", e)
    try:
        _register_kaisya_member_assistant()
    except Exception as e:
        LOG.warning("Could not register kaisya_member_assistant graph: %s", e)
    try:
        _register_isbn_ingest_aozora()
    except Exception as e:
        LOG.warning("Could not register isbn_ingest_aozora graph: %s", e)
    try:
        _register_isbn_ingest_gutenberg()
    except Exception as e:
        LOG.warning("Could not register isbn_ingest_gutenberg graph: %s", e)
    try:
        _register_isbn_ingest_ndl()
    except Exception as e:
        LOG.warning("Could not register isbn_ingest_ndl graph: %s", e)
    try:
        _register_isbn_ingest_hathitrust()
    except Exception as e:
        LOG.warning("Could not register isbn_ingest_hathitrust graph: %s", e)
    try:
        _register_isbn_ingest_open_library()
    except Exception as e:
        LOG.warning("Could not register isbn_ingest_open_library graph: %s", e)
    try:
        _register_isbn_ingest_internet_archive()
    except Exception as e:
        LOG.warning("Could not register isbn_ingest_internet_archive graph: %s", e)
    try:
        _register_ndl_image_ocr_ingest()
    except Exception as e:
        LOG.warning("Could not register ndl_image_ocr_ingest graph: %s", e)
    for _aria_node in [
        "attention_ingest",
        "request_ingest",
        "market_ingest",
        "money_flow_ingest",
        "emotion_ingest",
        "influence_ingest",
        "minimax_sweep",
    ]:
        try:
            _register_aria_graph(_aria_node)
        except Exception as e:
            LOG.warning("Could not register aria_%s graph: %s", _aria_node, e)
    try:
        _register_adsk_ingest_dataset()
    except Exception as e:
        LOG.warning("Could not register adsk_ingest_dataset graph: %s", e)
    try:
        _register_coverage_gap_bridge()
    except Exception as e:
        LOG.warning("Could not register coverage_gap_bridge graph: %s", e)
    try:
        _register_patent_ingest_uspto_weekly()
    except Exception as e:
        LOG.warning("Could not register patent_ingest_uspto_weekly graph: %s", e)
    try:
        _register_patent_blob_convert()
    except Exception as e:
        LOG.warning("Could not register patent_blob_convert graph: %s", e)
    try:
        _register_agent_runtime_lease_autopilot()
    except Exception as e:
        LOG.warning("Could not register agent_runtime_lease_autopilot graph: %s", e)
    try:
        _register_onion_crawl_seeds()
    except Exception as e:
        LOG.warning("Could not register onion_crawl_seeds graph: %s", e)
    try:
        _register_public_malak_crawl_ads()
    except Exception as e:
        LOG.warning("Could not register public_malak_crawl_ads graph: %s", e)
    try:
        _register_ransomware_actor_activity()
    except Exception as e:
        LOG.warning("Could not register ransomware_actor_activity graph: %s", e)
    try:
        _register_os_messaging_crawl_open_channels()
    except Exception as e:
        LOG.warning("Could not register os_messaging_crawl_open_channels graph: %s", e)
    try:
        _register_site_common_crawl_ingest()
    except Exception as e:
        LOG.warning("Could not register site_common_crawl_ingest graph: %s", e)
    try:
        _register_tsukuru_isic_pulse()
    except Exception as e:
        LOG.warning("Could not register tsukuru_isic_pulse graph: %s", e)
    try:
        _register_open_isic_classify_entity()
    except Exception as e:
        LOG.warning("Could not register open_isic_classify_entity graph: %s", e)
    try:
        _register_open_isic_hierarchical_classify()
    except Exception as e:
        LOG.warning("Could not register open_isic_hierarchical_classify graph: %s", e)
    try:
        _register_shosha_refresh_sanctions_list()
    except Exception as e:
        LOG.warning("Could not register shosha_refresh_sanctions_list graph: %s", e)
    try:
        _register_gameya_quality_loop()
    except Exception as e:
        LOG.warning("Could not register gameya_quality_loop graph: %s", e)


def _register_shosha_refresh_sanctions_list() -> None:
    """shosha.refreshSanctionsList StateGraph — Phase 5 daily CronJob (01:00 UTC)."""
    from kotodama.langgraph_graphs.shosha_refresh_sanctions_list import build_graph

    register_graph("shosha_refresh_sanctions_list", build_graph())
    LOG.info("Registered shosha_refresh_sanctions_list graph")


def _register_gameya_quality_loop() -> None:
    """gameya.qualityLoop StateGraph — browser game playtest improvement loop."""
    from kotodama.langgraph_graphs.gameya_quality_loop import build_graph

    register_graph("gameya_quality_loop", build_graph())
    LOG.info("Registered gameya_quality_loop graph")


def _register_tsukuru_isic_pulse() -> None:
    """tsukuru.isic.pulse generic StateGraph — replaces 21 ISIC BPMNs (daily)."""
    from kotodama.langgraph_graphs.tsukuru_isic_pulse import build_graph

    register_graph("tsukuru_isic_pulse", build_graph())
    LOG.info("Registered tsukuru_isic_pulse graph")


def _register_open_isic_classify_entity() -> None:
    """open_isic.classifyEntity generic StateGraph — routes to industry MCP tools."""
    from kotodama.langgraph_graphs.open_isic_classify_entity import build_graph

    register_graph("open_isic_classify_entity", build_graph())
    LOG.info("Registered open_isic_classify_entity graph")


def _register_open_isic_hierarchical_classify() -> None:
    """open_isic_hierarchical_classify StateGraph — hierarchical taxonomy drill-down."""
    from kotodama.langgraph_graphs.open_isic_hierarchical_classify import build_graph

    register_graph("open_isic_hierarchical_classify", build_graph())
    LOG.info("Registered open_isic_hierarchical_classify graph")


def _register_os_messaging_crawl_open_channels() -> None:
    """osMessaging.crawlOpenChannels StateGraph — Phase 5 CronJob (R/PT6H)."""
    from kotodama.langgraph_graphs.os_messaging_crawl_open_channels import build_graph

    register_graph("os_messaging_crawl_open_channels", build_graph())
    LOG.info("Registered os_messaging_crawl_open_channels graph")


def _register_site_common_crawl_ingest() -> None:
    """site.commonCrawl.ingest StateGraph — resident Common Crawl ingest."""
    from kotodama.langgraph_graphs.site_common_crawl_ingest import build_graph

    register_graph("site_common_crawl_ingest", build_graph())
    LOG.info("Registered site_common_crawl_ingest graph")


def _register_onion_crawl_seeds() -> None:
    """onion.crawlSeeds StateGraph — Phase 5 CronJob (R/PT6H)."""
    from kotodama.langgraph_graphs.onion_crawl_seeds import build_graph

    register_graph("onion_crawl_seeds", build_graph())
    LOG.info("Registered onion_crawl_seeds graph")


def _register_public_malak_crawl_ads() -> None:
    """publicMalak.crawlAds StateGraph — Phase 5 CronJob (R/PT6H)."""
    from kotodama.langgraph_graphs.public_malak_crawl_ads import build_graph

    register_graph("public_malak_crawl_ads", build_graph())
    LOG.info("Registered public_malak_crawl_ads graph")


def _register_ransomware_actor_activity() -> None:
    """Malak ransomware actor activity StateGraph — passive OSINT + Pregel scoring."""
    from kotodama.langgraph_graphs.ransomware_actor_activity import build_graph

    register_graph("ransomware_actor_activity", build_graph())
    LOG.info("Registered ransomware_actor_activity graph")


def _register_agent_runtime_lease_autopilot() -> None:
    """agent.runtime.leaseAutopilot StateGraph — Phase 5 CronJob (R/PT15M)."""
    from kotodama.langgraph_graphs.agent_runtime_lease_autopilot import build_graph

    register_graph("agent_runtime_lease_autopilot", build_graph())
    LOG.info("Registered agent_runtime_lease_autopilot graph")


def _register_coverage_gap_bridge() -> None:
    """coverage.gapBridge StateGraph — Phase 5 CronJob replacement (R/PT6H, 5-task chain)."""
    from kotodama.langgraph_graphs.coverage_gap_bridge import build_graph

    register_graph("coverage_gap_bridge", build_graph())
    LOG.info("Registered coverage_gap_bridge graph")


def _register_patent_ingest_uspto_weekly() -> None:
    """patent.ingestUsptoWeekly StateGraph — Phase 5 CronJob (Sunday midnight)."""
    from kotodama.langgraph_graphs.patent_ingest_uspto_weekly import build_graph

    register_graph("patent_ingest_uspto_weekly", build_graph())
    LOG.info("Registered patent_ingest_uspto_weekly graph")


def _register_patent_blob_convert() -> None:
    """patent.blobConvert StateGraph — Phase 5 CronJob (every 5 min)."""
    from kotodama.langgraph_graphs.patent_blob_convert import build_graph

    register_graph("patent_blob_convert", build_graph())
    LOG.info("Registered patent_blob_convert graph")


def _register_aria_graph(node: str) -> None:
    """aria.{node} StateGraph — Phase 5 CronJob replacement (R/PT4H)."""
    import importlib

    mod = importlib.import_module(f"kotodama.langgraph_graphs.aria_{node}")
    register_graph(f"aria_{node}", mod.build_graph())
    LOG.info("Registered aria_%s graph", node)


def _register_adsk_ingest_dataset() -> None:
    """adsk.ingestDataset StateGraph — Phase 5 CronJob replacement (monthly day 6)."""
    from kotodama.langgraph_graphs.adsk_ingest_dataset import build_graph

    register_graph("adsk_ingest_dataset", build_graph())
    LOG.info("Registered adsk_ingest_dataset graph")


def _register_isbn_ingest_aozora() -> None:
    """isbn.ingestAozora StateGraph — Phase 5 CronJob replacement (R/PT24H)."""
    from kotodama.langgraph_graphs.isbn_ingest_aozora import build_graph

    register_graph("isbn_ingest_aozora", build_graph())
    LOG.info("Registered isbn_ingest_aozora graph")


def _register_isbn_ingest_gutenberg() -> None:
    """isbn.ingestGutenberg StateGraph — Phase 5 CronJob replacement (R/PT24H)."""
    from kotodama.langgraph_graphs.isbn_ingest_gutenberg import build_graph

    register_graph("isbn_ingest_gutenberg", build_graph())
    LOG.info("Registered isbn_ingest_gutenberg graph")


def _register_isbn_ingest_ndl() -> None:
    """isbn.ingestNdl StateGraph — Phase 5 CronJob replacement (weekly Mon)."""
    from kotodama.langgraph_graphs.isbn_ingest_ndl import build_graph

    register_graph("isbn_ingest_ndl", build_graph())
    LOG.info("Registered isbn_ingest_ndl graph")


def _register_ndl_image_ocr_ingest() -> None:
    """NDL image-first WebP + OCR ingest, bounded per run."""
    from kotodama.langgraph_graphs.ndl_image_ocr_ingest import build_graph

    register_graph("ndl_image_ocr_ingest", build_graph())
    LOG.info("Registered ndl_image_ocr_ingest graph")


def _register_biblio_open_data_ingest() -> None:
    """Global bibliographic open-data source/record ingest."""
    from kotodama.langgraph_graphs.biblio_open_data_ingest import build_graph

    register_graph("biblio_open_data_ingest", build_graph())
    LOG.info("Registered biblio_open_data_ingest graph")


def _register_isbn_ingest_hathitrust() -> None:
    """isbn.ingestHathitrust StateGraph — Phase 5 CronJob replacement (monthly day 8)."""
    from kotodama.langgraph_graphs.isbn_ingest_hathitrust import build_graph

    register_graph("isbn_ingest_hathitrust", build_graph())
    LOG.info("Registered isbn_ingest_hathitrust graph")


def _register_isbn_ingest_open_library() -> None:
    """isbn.ingestOpenLibrary StateGraph — Phase 5 CronJob replacement (monthly day 5)."""
    from kotodama.langgraph_graphs.isbn_ingest_open_library import build_graph

    register_graph("isbn_ingest_open_library", build_graph())
    LOG.info("Registered isbn_ingest_open_library graph")


def _register_isbn_ingest_internet_archive() -> None:
    """isbn.ingestInternetArchive StateGraph — Phase 5 CronJob replacement (monthly day 12)."""
    from kotodama.langgraph_graphs.isbn_ingest_internet_archive import build_graph

    register_graph("isbn_ingest_internet_archive", build_graph())
    LOG.info("Registered isbn_ingest_internet_archive graph")


def _register_etzhayyim_company_ops() -> None:
    """etzhayyim Company Ops — Supervisor + HR/Finance/Legal/Sales/Governance multi-agent."""
    from kotodama.langgraph_graphs.etzhayyim_company_ops import build_graph

    register_graph("etzhayyim-company-ops", build_graph())
    LOG.info("Registered etzhayyim-company-ops graph")


def _register_lawfirm_marketing_ops() -> None:
    """lawfirm Marketing Ops — Supervisor + content/social/outreach/platform/analytics/event + BCI Rule 36 compliance gate."""
    from kotodama.langgraph_graphs.lawfirm_marketing_ops import build_graph

    register_graph("lawfirm-marketing-ops", build_graph())
    LOG.info("Registered lawfirm-marketing-ops graph")


def _register_kaisya_member_assistant() -> None:
    """kaisya Member Assistant — per-member chat surface (M365 / MCP / web), RACI-aware supervisor."""
    from kotodama.langgraph_graphs.kaisya_member_assistant import build_graph

    register_graph("kaisya-member-assistant", build_graph())
    LOG.info("Registered kaisya-member-assistant graph")


def _register_yoro_product_ingest() -> None:
    """Register yoro.productIngest LangGraph (generic public-retailer product ingest)."""
    from kotodama.langgraph_graphs.yoro_product_ingest import build_graph

    register_graph("yoro_product_ingest", build_graph())
    LOG.info("Registered yoro_product_ingest graph")


def _register_copyright_ingest() -> None:
    """copyright.ingest StateGraph — LangGraph port of BPMN copyright_{crossref,datacite}_ingest."""
    from kotodama.langgraph_graphs.copyright_ingest import build_graph

    register_graph("copyright_ingest", build_graph())
    LOG.info("Registered copyright_ingest graph")


def _register_copyright_fulltext() -> None:
    """copyright.fulltext StateGraph — Unpaywall CC-BY full text → vertex_work_blob → v_training_text."""
    from kotodama.langgraph_graphs.copyright_fulltext import build_graph

    register_graph("copyright_fulltext", build_graph())
    LOG.info("Registered copyright_fulltext graph")


def _register_shinshi_seed_gap_fill() -> None:
    """shinshi.seedGapFill StateGraph — Phase 5 CronJob replacement."""
    from kotodama.langgraph_graphs.shinshi_seed_gap_fill import build_graph

    register_graph("shinshi_seed_gap_fill", build_graph())
    LOG.info("Registered shinshi_seed_gap_fill graph")


def _register_yoro_platform_pulse() -> None:
    """yoro.platformPulse StateGraph — Phase 5 CronJob replacement (R/PT4H, v1+v2)."""
    from kotodama.langgraph_graphs.yoro_platform_pulse import build_graph

    register_graph("yoro_platform_pulse", build_graph())
    LOG.info("Registered yoro_platform_pulse graph")


def _register_animeka_autopilot() -> None:
    """animeka.autopilot StateGraph — Phase 5 CronJob replacement (R/PT15M)."""
    from kotodama.langgraph_graphs.animeka_autopilot import build_graph

    register_graph("animeka_autopilot", build_graph())
    LOG.info("Registered animeka_autopilot graph")


def _register_shinka_cron_tick() -> None:
    """shinka.cronTick StateGraph — Phase 5 CronJob replacement (R/PT15M, v1+v2+v3)."""
    from kotodama.langgraph_graphs.shinka_cron_tick import build_graph

    register_graph("shinka_cron_tick", build_graph())
    LOG.info("Registered shinka_cron_tick graph")


def _register_wellbecoming_process_mining() -> None:
    """wellbecoming.processMining StateGraph — Phase 5 CronJob replacement (R/PT6H)."""
    from kotodama.langgraph_graphs.wellbecoming_process_mining import build_graph

    register_graph("wellbecoming_process_mining", build_graph())
    LOG.info("Registered wellbecoming_process_mining graph")


def _register_wellbecoming_detect_bottleneck() -> None:
    """wellbecoming.detectBottleneck StateGraph — Phase 5 CronJob replacement (R/PT1H)."""
    from kotodama.langgraph_graphs.wellbecoming_detect_bottleneck import build_graph

    register_graph("wellbecoming_detect_bottleneck", build_graph())
    LOG.info("Registered wellbecoming_detect_bottleneck graph")


def _register_wellbecoming_proactive_connect() -> None:
    """wellbecoming.proactiveConnect StateGraph — Phase 5 CronJob replacement (R/PT2H)."""
    from kotodama.langgraph_graphs.wellbecoming_proactive_connect import build_graph

    register_graph("wellbecoming_proactive_connect", build_graph())
    LOG.info("Registered wellbecoming_proactive_connect graph")


def _register_wellbecoming_floor_violation_alert() -> None:
    """wellbecoming.floorViolationAlert StateGraph — Phase 5 CronJob replacement (R/PT30M)."""
    from kotodama.langgraph_graphs.wellbecoming_floor_violation_alert import build_graph

    register_graph("wellbecoming_floor_violation_alert", build_graph())
    LOG.info("Registered wellbecoming_floor_violation_alert graph")


def _register_wellbecoming_minimax_sweep() -> None:
    """wellbecoming.minimaxSweep StateGraph — Phase 5 CronJob replacement (R/PT5M)."""
    from kotodama.langgraph_graphs.wellbecoming_minimax_sweep import build_graph

    register_graph("wellbecoming_minimax_sweep", build_graph())
    LOG.info("Registered wellbecoming_minimax_sweep graph")


def _register_wellbecoming_belief_influence_propagate() -> None:
    """wellbecoming.beliefInfluencePropagate StateGraph — Phase 5 CronJob replacement (R/PT1H)."""
    from kotodama.langgraph_graphs.wellbecoming_belief_influence_propagate import build_graph

    register_graph("wellbecoming_belief_influence_propagate", build_graph())
    LOG.info("Registered wellbecoming_belief_influence_propagate graph")


def _register_wellbecoming_belief_noise_inject() -> None:
    """wellbecoming.beliefNoiseInject StateGraph — Phase 5 CronJob replacement (R/PT1H)."""
    from kotodama.langgraph_graphs.wellbecoming_belief_noise_inject import build_graph

    register_graph("wellbecoming_belief_noise_inject", build_graph())
    LOG.info("Registered wellbecoming_belief_noise_inject graph")


def _register_wellbecoming_belief_restoring_capture() -> None:
    """wellbecoming.beliefRestoringCapture StateGraph — Phase 5 CronJob replacement (R/PT1H)."""
    from kotodama.langgraph_graphs.wellbecoming_belief_restoring_capture import build_graph

    register_graph("wellbecoming_belief_restoring_capture", build_graph())
    LOG.info("Registered wellbecoming_belief_restoring_capture graph")


def _register_wellbecoming_trust_weight_update() -> None:
    """wellbecoming.trustWeightUpdate StateGraph — Phase 5 CronJob replacement (R/PT1H)."""
    from kotodama.langgraph_graphs.wellbecoming_trust_weight_update import build_graph

    register_graph("wellbecoming_trust_weight_update", build_graph())
    LOG.info("Registered wellbecoming_trust_weight_update graph")


def _register_shosha_trade_idea_synthesize() -> None:
    """shosha.tradeIdeaSynthesize StateGraph — Phase 5 CronJob replacement."""
    from kotodama.langgraph_graphs.shosha_trade_idea_synthesize import build_graph

    register_graph("shosha_trade_idea_synthesize", build_graph())
    LOG.info("Registered shosha_trade_idea_synthesize graph")


def _register_shosha_daily_report() -> None:
    """shosha.dailyReport StateGraph — Phase 5 CronJob replacement."""
    from kotodama.langgraph_graphs.shosha_daily_report import build_graph

    register_graph("shosha_daily_report", build_graph())
    LOG.info("Registered shosha_daily_report graph")


def _register_ki_synthesis() -> None:
    """ki.synthesize.v1 StateGraph — LangGraph port of ki_synthesis_graph."""
    from kotodama.primitives.ki_synthesis_graph import _build_graph

    register_graph("ki.synthesize.v1", _build_graph())
    LOG.info("Registered ki.synthesize.v1 graph")


def _register_webmk_proposal() -> None:
    """webmk.createProposal StateGraph — LangGraph port of webmk_worker_main."""
    from kotodama.langgraph_graphs.webmk_proposal import build_graph

    register_graph("webmk_create_proposal", build_graph())
    LOG.info("Registered webmk_create_proposal graph")


def _register_ki_cycle() -> None:
    """ki.cycle.v1 StateGraph — full vascular synthesis cycle (absorb→synthesize→bloom?→ring)."""
    from kotodama.langgraph_graphs.ki_cycle import build_graph

    register_graph("ki.cycle.v1", build_graph())
    LOG.info("Registered ki.cycle.v1 graph")


def _register_saikin_cycle() -> None:
    """saikin.cycle.v1 StateGraph — horizontal-transfer cycle (probe→transfer→colony|lyse→handoff)."""
    from kotodama.langgraph_graphs.saikin_cycle import build_graph

    register_graph("saikin.cycle.v1", build_graph())
    LOG.info("Registered saikin.cycle.v1 graph")


def _register_newsletter_send_campaign() -> None:
    """newsletter_send_campaign StateGraph — re-export build_newsletter_graph() from worker_main."""
    from kotodama.newsletter_worker_main import build_newsletter_graph

    register_graph("newsletter_send_campaign", build_newsletter_graph())
    LOG.info("Registered newsletter_send_campaign graph")


def _register_koke_cycle() -> None:
    """koke.cycle.v1 — photosynthesis cycle (scan → fix → classify → handoff)."""
    from kotodama.langgraph_graphs.koke_cycle import build_graph

    register_graph("koke.cycle.v1", build_graph())
    LOG.info("Registered koke.cycle.v1 graph")


def _register_organism_single_task_chains() -> None:
    """Wrap myco-yeast organism actor tasks (kobo/kabi/kinoko/hakkou) as
    one-node LangGraph chains so the bpmn-dispatcher can route via
    routing_target='langgraph'."""
    from kotodama.langgraph_graphs._single_task_wrapper import build_single_task_graph
    from kotodama.kobo_worker_main import (
        task_bud_agent,
        task_sporulate,
        task_germinate,
    )
    from kotodama.kabi_worker_main import task_anastomosis_probe
    from kotodama.kinoko_worker_main import task_check_flow_threshold
    from kotodama.hakkou_worker_main import (
        task_create_ferment_record,
        task_llm_transform,
        task_finalize_ferment,
    )

    pairs = [
        ("kobo.budAgent.v1", task_bud_agent),
        ("kobo.sporulate.v1", task_sporulate),
        ("kobo.germinate.v1", task_germinate),
        ("kabi.fusionProbe.v1", task_anastomosis_probe),
        ("kinoko.formBlock.v1", task_check_flow_threshold),
        ("hakkou.createFerment.v1", task_create_ferment_record),
        ("hakkou.llmTransform.v1", task_llm_transform),
        ("hakkou.finalizeFerment.v1", task_finalize_ferment),
    ]
    for assistant_id, fn in pairs:
        register_graph(assistant_id, build_single_task_graph(fn))
    LOG.info("Registered %d organism single-task chains", len(pairs))


def _register_shosha_agent_loop() -> None:
    """shosha.agentLoop StateGraph — LangGraph port of task_shosha_agent_chat."""
    from kotodama.langgraph_graphs.shosha_agent_loop import build_graph

    register_graph("shosha_agent_loop", build_graph())
    LOG.info("Registered shosha_agent_loop graph")


def _register_shosha_market_intelligence() -> None:
    """shosha.marketIntelligenceIngest StateGraph — Phase 5 CronJob replacement."""
    from kotodama.langgraph_graphs.shosha_market_intelligence import build_graph

    register_graph("shosha_market_intelligence", build_graph())
    LOG.info("Registered shosha_market_intelligence graph")


def _register_shosha_trade_book_recompute() -> None:
    """shosha.tradeBookRecompute StateGraph — Phase 5 CronJob replacement."""
    from kotodama.langgraph_graphs.shosha_trade_book_recompute import build_graph

    register_graph("shosha_trade_book_recompute", build_graph())
    LOG.info("Registered shosha_trade_book_recompute graph")


def _register_shosha_react_upstream() -> None:
    """shosha.reactToUpstream StateGraph — Phase 5 CronJob replacement."""
    from kotodama.langgraph_graphs.shosha_react_upstream import build_graph

    register_graph("shosha_react_upstream", build_graph())
    LOG.info("Registered shosha_react_upstream graph")


def _register_pregel_email_triage() -> None:
    """pregel email triage graph (parse_email→classify_intent→detect_deps→write_vertex)."""
    from kotodama.pregel.graph import build_graph

    register_graph("pregel-email-triage", build_graph())
    LOG.info("Registered pregel-email-triage graph")


def _register_echo_graph() -> None:
    """Minimal echo graph for smoke-testing the /runs API."""
    try:
        from langgraph.graph import END, StateGraph
        from typing import TypedDict

        class EchoState(TypedDict):
            input: str
            output: str

        def echo_node(state: EchoState) -> dict:
            return {"output": f"echo: {state.get('input', '')}"}

        builder = StateGraph(EchoState)
        builder.add_node("echo", echo_node)
        builder.set_entry_point("echo")
        builder.add_edge("echo", END)
        graph = builder.compile()
        register_graph("echo", graph)
        LOG.info("Registered builtin echo graph")
    except Exception as e:
        LOG.warning("Could not build echo graph: %s", e)

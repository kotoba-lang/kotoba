"""HTTP training server — runs on the H100 NVL training pod (ADR 2605092345,
2026-05-09). The H100 pod is *training-only*: Oka SFT / LoRA / distill /
eval and the Baien LoRA-on-bf16-master / projector grafts (ADR 2605092350)
all live here. Inference (ComfyUI / vLLM / LiteLLM) continues on the RunPod
6000 Ada unified pod (ADR-2605010000) and is not collapsed into this server.

ADR-2605070700 Addendum-of-Addendum 2026-05-07; superseded for the GPU-side
pod assignment by ADR 2605092345 (H100 trainer split).

Wire:
  CPU pod (mitama-training-pool, LangServer primitive task_train_*_run)
    ↓ HTTP POST {pod_proxy}/train/run        (this server, port 8003)
    ↓ background thread → runpod_handler(event)
    ↓ vertex_training_run + vertex_training_checkpoint INSERT (RW)
    ↓ B2 PUT for weights
  CPU pod polls {pod_proxy}/train/status/{job_id} until terminal.

The handler runs the same `kotodama.primitives.training_run.runpod_handler`
that the (deprecated) Serverless trainer image used. No code path changes
inside the trainer; only the wire-format wrapper is different.

Endpoints:
  POST /train/run            body = {"input": {...}}     → {"id": str, "status": "IN_QUEUE"}
  GET  /train/status/{id}                                → {"id", "status", "output"?, "error"?}
  GET  /healthz                                          → {"ok": true}

Status enum (mirrors RunPod Serverless so the CPU client code is identical):
  IN_QUEUE → IN_PROGRESS → COMPLETED   (or FAILED on uncaught exception)

Job state lives in-memory (single-pod, single-server, dies on pod restart).
That's fine — the canonical lineage is `vertex_training_run` (RW, persistent),
which the handler writes regardless. If the pod restarts mid-job, the run row
stays at status='running' until manually patched (degraded mode noted in ADR).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import traceback
import uuid
from typing import Any

LOG = logging.getLogger("training_http_server")

_PORT = int(os.environ.get("TRAINING_HTTP_PORT", "8003"))
_HOST = os.environ.get("TRAINING_HTTP_HOST", "0.0.0.0")
_AUTH_TOKEN = os.environ.get("TRAINING_POD_AUTH_TOKEN", "").strip()

# Job table — id → {"status", "input", "output", "error", "started_at", "ended_at"}.
_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _set_job(job_id: str, **fields: Any) -> None:
    with _JOBS_LOCK:
        cur = _JOBS.get(job_id) or {}
        cur.update(fields)
        _JOBS[job_id] = cur


def _get_job(job_id: str) -> dict[str, Any] | None:
    with _JOBS_LOCK:
        cur = _JOBS.get(job_id)
        return dict(cur) if cur is not None else None


def _run_job_blocking(job_id: str, payload: dict) -> None:
    """Background-thread entry: dispatches to runpod_handler and records the
    result on the job row. All exceptions become FAILED + traceback string.
    """
    from kotodama.primitives.training_run import runpod_handler

    _set_job(job_id, status="IN_PROGRESS", started_at=time.time())
    try:
        result = runpod_handler({"input": payload, "id": job_id})
        _set_job(job_id, status="COMPLETED", output=result, ended_at=time.time())
        LOG.info("training_http_server job=%s COMPLETED", job_id)
    except Exception as e:  # noqa: BLE001 — surface every failure to the client
        tb = traceback.format_exc()
        _set_job(job_id, status="FAILED", error={"message": str(e), "traceback": tb}, ended_at=time.time())
        LOG.error("training_http_server job=%s FAILED: %s\n%s", job_id, e, tb)


def _build_app() -> Any:
    """Builds a Starlette app. Lazy import keeps this module loadable on
    pods that don't have starlette installed (e.g. CPU orchestrator pool).
    """
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    def _check_auth(req: Request) -> JSONResponse | None:
        if not _AUTH_TOKEN:
            return None  # token unset — open mode (RunPod proxy URL is private path-based; OK for dev)
        provided = (req.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        if provided != _AUTH_TOKEN:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return None

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "host": _HOST, "port": _PORT, "active_jobs": len(_JOBS),
                             "auth": "bearer" if _AUTH_TOKEN else "open"})

    async def submit(req: Request) -> JSONResponse:
        deny = _check_auth(req)
        if deny:
            return deny
        try:
            body = await req.json()
        except Exception as e:
            return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
        if not isinstance(body, dict) or "input" not in body:
            return JSONResponse({"error": "body must be {\"input\": {...}}"}, status_code=400)
        payload = body["input"] if isinstance(body["input"], dict) else {}

        job_id = uuid.uuid4().hex
        _set_job(job_id, status="IN_QUEUE", input=payload, queued_at=time.time())
        threading.Thread(target=_run_job_blocking, args=(job_id, payload), daemon=True).start()
        return JSONResponse({"id": job_id, "status": "IN_QUEUE"})

    async def status(req: Request) -> JSONResponse:
        deny = _check_auth(req)
        if deny:
            return deny
        job_id = req.path_params["job_id"]
        row = _get_job(job_id)
        if row is None:
            return JSONResponse({"error": f"unknown job_id={job_id!r}"}, status_code=404)
        out: dict[str, Any] = {"id": job_id, "status": row.get("status", "UNKNOWN")}
        if "output" in row:
            out["output"] = row["output"]
        if "error" in row:
            out["error"] = row["error"]
        if "queued_at" in row:
            out["queued_at"] = row["queued_at"]
        if "started_at" in row:
            out["started_at"] = row["started_at"]
        if "ended_at" in row:
            out["ended_at"] = row["ended_at"]
        return JSONResponse(out)

    return Starlette(
        debug=False,
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Route("/train/run", submit, methods=["POST"]),
            Route("/train/status/{job_id}", status, methods=["GET"]),
        ],
    )


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,
    )
    try:
        import uvicorn  # type: ignore
    except ImportError:
        raise RuntimeError(
            "uvicorn not installed — required for training_http_server. "
            "Install in the unified pod image."
        )
    LOG.info("training_http_server binding on %s:%d", _HOST, _PORT)
    uvicorn.run(_build_app(), host=_HOST, port=_PORT, log_level="info")


if __name__ == "__main__":
    main()

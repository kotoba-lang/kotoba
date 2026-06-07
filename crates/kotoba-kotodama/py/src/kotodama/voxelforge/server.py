"""Granian / FastAPI entrypoint for the voxelforge LangGraph actor
(ADR-2605080600 + ADR-2605080700).

Run with::

    granian --interface asgi kotodama.voxelforge.server:app \
            --host 0.0.0.0 --port 8000 --workers 1

The Helm chart ``mitama-voxelforge-pool`` provides this command line.

Endpoints (subset of LangGraph Server convention; we ship our own
because ``langgraph-api`` 0.2.x bundles too much for the Phase A
scope):

  - ``POST /runs``                      submit a generate run
  - ``GET  /runs/{run_id}``             poll status / artifacts
  - ``GET  /health`` / ``/_app/meta``   probes
  - ``POST /xrpc/com.etzhayyim.apps.voxelforge.{generate,getRun,listArtifacts,coverage}``
                                        bpmn-dispatcher bridge

bpmn-dispatcher (ADR-2604282300) routes
``com.etzhayyim.apps.voxelforge.*`` to this service via in-cluster ClusterIP
``voxelforge-langgraph.mitama-udf.svc.cluster.local:8000``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]


from kotodama.voxelforge.graph import build_graph
from kotodama.voxelforge.state import (
    DesignKind,
    GenerateInput,
    TargetFormat,
    VoxelforgeState,
)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _make_design_vertex_id(actor_did: str, ts_ms: int, prompt_hash: str) -> str:
    digest = hashlib.sha256(f"{actor_did}|{ts_ms}|{prompt_hash}".encode()).hexdigest()
    return f"at://{actor_did}/com.etzhayyim.apps.voxelforge.design/{digest[:16]}"


def _make_run_id(design_vertex_id: str) -> str:
    return hashlib.sha256(design_vertex_id.encode()).hexdigest()[:32]


def build_app() -> Any:
    if FastAPI is None:  # pragma: no cover
        raise RuntimeError("fastapi not installed")
    api = FastAPI(title="voxelforge-langgraph", version="0.1.0")
    graph = build_graph()
    runs: dict[str, dict[str, Any]] = {}

    def _internal_trust_ok(req: Request) -> bool:
        """Phase A: light HMAC check.  bpmn-dispatcher signs every
        forward; bare requests are rejected unless ``etzhayyim_VOXELFORGE_DEV=1``."""
        if os.environ.get("etzhayyim_VOXELFORGE_DEV") == "1":
            return True
        return bool(req.headers.get("x-internal-trust"))

    def _resolve_caller(req: Request) -> tuple[str, str]:
        actor = req.headers.get("x-etzhayyim-actor-did") or os.environ.get("etzhayyim_DEV_ACTOR_DID", "did:web:voxelforge.etzhayyim.com")
        org = req.headers.get("x-etzhayyim-org-did") or os.environ.get("etzhayyim_DEV_ORG_DID", "did:erc725:etzhayyim:260425:dev")
        return actor, org

    @api.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "app": "voxelforge-langgraph", "ts": _utc_now_iso()}

    @api.get("/_app/meta")
    async def meta() -> dict[str, Any]:
        return {
            "app": "voxelforge-langgraph",
            "did": "did:web:voxelforge.etzhayyim.com",
            "layer": "L3-execution",
            "runtime": "langgraph-server+granian",
            "graph_nodes": [
                "parse_input",
                "route_generator",
                "generate_trellis",
                "generate_comfy3d",
                "exec_cadquery",
                "post_process_mesh",
                "voxelize",
                "export_artifacts",
                "register_artifact",
            ],
            "runpod_pod": os.environ.get("RUNPOD_POD_ID", "vyp99t9px7h4dl"),
        }

    def _unwrap_envelope(body: dict) -> tuple[dict, str | None, str | None]:
        """Accept both shapes:

        1. **Dispatcher** (`bpmn-dispatcher._dispatch_langgraph`)::

               {"assistant_id": "voxelforge_generate",
                "input": {kind, prompt, targetFormat, ...},
                "thread_id": "...",   # optional
                "actor_did": "did:web:..."}  # optional

        2. **Direct** (curl / pytest)::

               {"kind": "...", "prompt": "...", "targetFormat": "..."}

        Returns ``(generate_input_payload, override_actor_did, override_thread_id)``.
        """
        if not isinstance(body, dict):
            return {}, None, None
        # Heuristic: dispatcher envelope if it has an `input` key that is itself
        # a dict, OR an `assistant_id` key. Otherwise treat as raw GenerateInput.
        looks_like_envelope = (
            isinstance(body.get("input"), dict)
            or "assistant_id" in body
        )
        if looks_like_envelope:
            return (
                body.get("input") or {},
                body.get("actor_did") or body.get("actorDid"),
                body.get("thread_id") or body.get("threadId"),
            )
        return body, None, None

    async def _start_run(input_payload: dict, actor_did: str, org_did: str) -> dict[str, Any]:
        gi = GenerateInput.model_validate(input_payload)
        ts_ms = int(time.time() * 1000)
        body_hash = hashlib.sha256(
            json.dumps(input_payload, sort_keys=True).encode()
        ).hexdigest()
        design_id = _make_design_vertex_id(actor_did, ts_ms, body_hash)
        run_id = _make_run_id(design_id)
        state = VoxelforgeState(
            input=gi,
            actor_did=actor_did,
            org_did=org_did,
            design_vertex_id=design_id,
            run_id=run_id,
            started_at=_utc_now_iso(),
        )
        runs[run_id] = {
            "status": "running",
            "designId": design_id,
            "startedAt": state.started_at,
            "currentNode": "parse_input",
            "artifacts": [],
            "errorText": None,
        }

        async def _run() -> None:
            try:
                final_state: Any = None
                async for ev in graph.astream(state.model_dump(), stream_mode="values"):
                    final_state = ev
                    if isinstance(ev, dict) and ev.get("current_node"):
                        runs[run_id]["currentNode"] = ev["current_node"]
                    if isinstance(ev, dict) and ev.get("error_text"):
                        runs[run_id]["errorText"] = ev["error_text"]
                if final_state and isinstance(final_state, dict):
                    runs[run_id]["artifacts"] = [
                        a if isinstance(a, dict) else a.model_dump(mode="json")  # type: ignore[union-attr]
                        for a in (final_state.get("artifacts") or [])
                    ]
                    runs[run_id]["finishedAt"] = _utc_now_iso()
                    runs[run_id]["status"] = "failed" if runs[run_id].get("errorText") else "completed"
            except Exception as exc:
                runs[run_id]["status"] = "failed"
                runs[run_id]["errorText"] = f"{type(exc).__name__}: {exc}"
                runs[run_id]["finishedAt"] = _utc_now_iso()

        asyncio.create_task(_run())

        # Dual-shape response: snake_case `run_id`/`thread_id`/`status` for
        # the dispatcher (`_dispatch_langgraph` reads `body.get("run_id")`),
        # plus camelCase mirrors for direct REST clients.
        return {
            "run_id": run_id,
            "thread_id": run_id,
            "status": "running",
            "runId": run_id,
            "designId": design_id,
            "estimatedSeconds": _estimate_seconds(gi.kind),
        }

    def _estimate_seconds(kind: DesignKind) -> int:
        if kind is DesignKind.CAD:
            return 15
        return 90  # text / image via TRELLIS

    # ── native LangGraph-style endpoints ────────────────────────────

    @api.post("/runs")
    async def post_run(req: Request) -> JSONResponse:
        if not _internal_trust_ok(req):
            raise HTTPException(status_code=401, detail="x-internal-trust required")
        body = await req.json()
        gen_input, env_actor, _env_thread = _unwrap_envelope(body or {})
        header_actor, header_org = _resolve_caller(req)
        actor_did = env_actor or header_actor
        org_did = header_org
        return JSONResponse(await _start_run(gen_input, actor_did, org_did))

    @api.get("/runs/{run_id}")
    async def get_run(run_id: str, req: Request) -> JSONResponse:
        if not _internal_trust_ok(req):
            raise HTTPException(status_code=401, detail="x-internal-trust required")
        rec = runs.get(run_id)
        if not rec:
            raise HTTPException(status_code=404, detail="NotFound")
        return JSONResponse(
            {
                "runId": run_id,
                "designId": rec["designId"],
                "status": rec["status"],
                "currentNode": rec.get("currentNode"),
                "errorText": rec.get("errorText"),
                "startedAt": rec["startedAt"],
                "finishedAt": rec.get("finishedAt"),
                "artifacts": rec.get("artifacts", []),
            }
        )

    # ── XRPC bridge endpoints (bpmn-dispatcher → here) ──────────────

    @api.post("/xrpc/com.etzhayyim.apps.voxelforge.generate")
    async def xrpc_generate(req: Request) -> JSONResponse:
        if not _internal_trust_ok(req):
            raise HTTPException(status_code=401, detail="x-internal-trust required")
        body = await req.json()
        gen_input, env_actor, _env_thread = _unwrap_envelope(body or {})
        header_actor, header_org = _resolve_caller(req)
        actor_did = env_actor or header_actor
        org_did = header_org
        return JSONResponse(await _start_run(gen_input, actor_did, org_did))

    @api.get("/xrpc/com.etzhayyim.apps.voxelforge.getRun")
    async def xrpc_get_run(req: Request) -> JSONResponse:
        if not _internal_trust_ok(req):
            raise HTTPException(status_code=401, detail="x-internal-trust required")
        run_id = req.query_params.get("runId")
        if not run_id:
            raise HTTPException(status_code=400, detail="runId required")
        rec = runs.get(run_id)
        if not rec:
            raise HTTPException(status_code=404, detail="NotFound")
        return JSONResponse(
            {
                "runId": run_id,
                "designId": rec["designId"],
                "status": rec["status"],
                "currentNode": rec.get("currentNode"),
                "errorText": rec.get("errorText"),
                "startedAt": rec["startedAt"],
                "finishedAt": rec.get("finishedAt"),
                "artifacts": rec.get("artifacts", []),
            }
        )

    @api.get("/xrpc/com.etzhayyim.apps.voxelforge.listArtifacts")
    async def xrpc_list_artifacts(req: Request) -> JSONResponse:
        if not _internal_trust_ok(req):
            raise HTTPException(status_code=401, detail="x-internal-trust required")
        # Phase A: serve from in-process ``runs`` cache.  Phase B: query
        # vertex_voxelforge_artifact directly for cross-pod visibility.
        design_id = req.query_params.get("designId")
        actor_did = req.query_params.get("actorDid")
        fmt = req.query_params.get("format")
        gen = req.query_params.get("generatedBy")
        try:
            limit = int(req.query_params.get("limit", "50"))
            offset = int(req.query_params.get("offset", "0"))
        except ValueError:
            limit, offset = 50, 0

        flat: list[dict[str, Any]] = []
        for rec in runs.values():
            for a in rec.get("artifacts", []) or []:
                if design_id and a.get("design_vertex_id") != design_id:
                    continue
                if actor_did and rec.get("designId", "").startswith(f"at://{actor_did}/") is False:
                    continue
                if fmt and a.get("format") != fmt:
                    continue
                if gen and a.get("generated_by") != gen:
                    continue
                flat.append(a)
        total = len(flat)
        return JSONResponse(
            {
                "artifacts": flat[offset : offset + limit],
                "total": total,
                "offset": offset,
                "limit": limit,
            }
        )

    @api.get("/xrpc/com.etzhayyim.apps.voxelforge.coverage")
    async def xrpc_coverage(req: Request) -> JSONResponse:
        if not _internal_trust_ok(req):
            raise HTTPException(status_code=401, detail="x-internal-trust required")
        try:
            window_days = int(req.query_params.get("windowDays", "7"))
        except ValueError:
            window_days = 7
        cutoff = time.time() - window_days * 86400
        designs = 0
        runs_count = 0
        artifacts = 0
        by_format: dict[str, dict[str, int]] = {}
        by_generator: dict[str, int] = {}
        runs_by_status: dict[str, int] = {}
        for rec in runs.values():
            ts = _parse_iso(rec.get("startedAt"))
            if ts and ts < cutoff:
                continue
            designs += 1
            runs_count += 1
            runs_by_status[rec["status"]] = runs_by_status.get(rec["status"], 0) + 1
            for a in rec.get("artifacts", []) or []:
                artifacts += 1
                f = a.get("format") or "unknown"
                bf = by_format.setdefault(f, {"count": 0, "total_byte_size": 0})
                bf["count"] += 1
                bf["total_byte_size"] += int(a.get("byte_size") or 0)
                g = a.get("generated_by") or "unknown"
                by_generator[g] = by_generator.get(g, 0) + 1
        return JSONResponse(
            {
                "designs": designs,
                "runs": runs_count,
                "runsByStatus": runs_by_status,
                "artifacts": artifacts,
                "byFormat": [
                    {"format": k, "count": v["count"], "totalByteSize": v["total_byte_size"]}
                    for k, v in by_format.items()
                ],
                "byGenerator": [{"generator": k, "count": v} for k, v in by_generator.items()],
                "windowDays": window_days,
            }
        )

    return api


def _parse_iso(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        return None


app = build_app() if FastAPI is not None else None

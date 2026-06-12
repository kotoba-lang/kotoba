"""
etzhayyim.ops — Zeebe task handler: submit to LangGraph etzhayyim-company-ops.

Task type: etzhayyim.ops.submit

Input variables:
  task_type      str   e.g. "hr.onboard", "finance.journal", "governance.daily"
  payload        dict  domain-specific data
  requester_did  str   (optional) DID of initiator

Output variables:
  result         dict  domain agent result
  action_items   list  human-review items
  omega_score    float governance Ω(t) (only if domain=governance)
  floor_violated bool  (only if domain=governance)
  ok             bool
  error          str   (if not ok)

Routing: POST /runs to LangGraph Server (langgraph_server_app) in-process or
via LANGGRAPH_SERVER_URL env var for out-of-process deployment.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

LOG = logging.getLogger("etzhayyim.ops")

_ASSISTANT_ID = "etzhayyim-company-ops"

# If running in the same pod as langgraph_server_app, prefer in-process call.
# Set LANGGRAPH_SERVER_URL=http://localhost:8001 to use HTTP instead.
_LANGGRAPH_URL = os.environ.get("LANGGRAPH_SERVER_URL", "")


def _run_in_process(task_type: str, payload: dict, requester_did: str, thread_id: str) -> dict:
    """Run graph directly in-process (preferred: same pod, no HTTP hop)."""
    from kotodama.langgraph_graphs.etzhayyim_company_ops import build_graph
    graph = build_graph()
    state_in = {
        "task_type": task_type,
        "payload": payload,
        "thread_id": thread_id,
        "requester_did": requester_did,
    }
    out = graph.invoke(state_in)
    return dict(out)


def _run_via_http(task_type: str, payload: dict, requester_did: str, thread_id: str) -> dict:
    """POST /runs to LangGraph Server HTTP (out-of-process deployment)."""
    import urllib.request
    body = json.dumps({
        "assistant_id": _ASSISTANT_ID,
        "thread_id": thread_id,
        "actor_did": requester_did or f"did:web:etzhayyim.etzhayyim.com",
        "input": {
            "task_type": task_type,
            "payload": payload,
            "requester_did": requester_did,
        },
    }).encode()
    req = urllib.request.Request(
        f"{_LANGGRAPH_URL}/runs",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        run = json.loads(resp.read())

    run_id = run.get("run_id") or run.get("vertex_id", "")
    if not run_id:
        return {"ok": False, "error": "no run_id in POST /runs response"}

    # Poll until done (max 170s)
    deadline = time.time() + 170
    while time.time() < deadline:
        time.sleep(3)
        poll_req = urllib.request.Request(
            f"{_LANGGRAPH_URL}/runs/{run_id}",
            method="GET",
        )
        with urllib.request.urlopen(poll_req, timeout=30) as poll_resp:
            status_body = json.loads(poll_resp.read())
        status = status_body.get("status", "pending")
        if status == "success":
            return status_body.get("output") or {"ok": True}
        if status == "error":
            return {"ok": False, "error": status_body.get("error_message", "unknown")}

    return {"ok": False, "error": "timeout waiting for LangGraph run"}


async def task_etzhayyim_ops_submit(
    task_type: str = "governance.daily",
    payload: dict | None = None,
    requester_did: str = "",
) -> dict:
    """
    Zeebe task handler: etzhayyim.ops.submit

    Submits a company-ops task to the LangGraph etzhayyim-company-ops graph
    (Supervisor → HR/Finance/Legal/Sales/Governance domain agent → audit).
    """
    import asyncio

    payload = payload or {}
    thread_id = f"etzhayyim-{task_type}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"

    LOG.info("etzhayyim.ops.submit task_type=%s thread=%s", task_type, thread_id)

    try:
        if _LANGGRAPH_URL:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _run_via_http, task_type, payload, requester_did, thread_id
            )
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _run_in_process, task_type, payload, requester_did, thread_id
            )
    except Exception as exc:
        LOG.error("etzhayyim.ops.submit failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    return {
        "result":        result.get("result", {}),
        "action_items":  result.get("action_items", []),
        "omega_score":   result.get("omega_score"),
        "floor_violated": result.get("floor_violated", False),
        "ok":            result.get("ok", True),
        "error":         result.get("error"),
    }


def register(app: Any) -> None:
    """Register etzhayyim.ops.submit with the Zeebe worker."""
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="etzhayyim.ops.submit", timeout_ms=190_000, max_jobs_to_activate=2)
    async def _handle(task_type: str = "governance.daily", payload: dict | None = None,
                      requester_did: str = "") -> dict:
        return await task_etzhayyim_ops_submit(
            task_type=task_type,
            payload=payload or {},
            requester_did=requester_did,
        )

    LOG.info("Registered task: etzhayyim.ops.submit")

"""
Zeebe userTask → vertex_human_task sink (tasklist backing store).

Camunda Tasklist is not deployed on our Vultr Zeebe 8.6.39 cluster
(see 50-infra/vultr/zeebe/zeebe.yaml). Without Tasklist REST, the
kaisya portal and other actor UIs cannot list or complete user tasks.

This module is the bridge: it activates `io.camunda.zeebe:userTask`
jobs via the gateway's streaming ActivateJobs RPC, mirrors each one
into `vertex_human_task`, and holds the job lock (24h timeout) until
the portal calls `complete_user_task(job_key, variables)`.

Rollout (kaisya BPMN-as-actor, ADR-0056):
  1. Launch `run_user_task_sink_loop()` alongside `watcher_loop` in
     `dispatcher_main.make_app()` — same asyncio loop, one channel.
  2. Add the `POST /zeebe/complete-user-task` route in the dispatcher
     (see `register_routes` below).
  3. Deploy the dispatcher; verify with:
        kubectl -n mitama-udf logs deploy/bpmn-dispatcher --tail 50 \\
          | grep user_task_sink
     and after a kaisya process start, confirm a row shows up in
     `vertex_human_task WHERE owner_did = 'did:web:bpmn.etzhayyim.com'`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

try:  # noqa: SIM105
    from grpc import aio as grpc_aio
    from zeebe_grpc import gateway_pb2, gateway_pb2_grpc
except ImportError:  # pragma: no cover — dispatcher image carries these
    grpc_aio = None  # type: ignore[assignment]
    gateway_pb2 = None  # type: ignore[assignment]
    gateway_pb2_grpc = None  # type: ignore[assignment]

from kotodama.kotoba_datomic import get_kotoba_client
from datetime import datetime, timezone

LOG = logging.getLogger("user_task_sink")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENTGATEWAY_MCP_URL = os.environ.get(
    "AGENTGATEWAY_MCP_URL",
    "http://agentgateway-mcp.mitama-udf.svc.cluster.local:8080",
)
USER_TASK_JOB_TYPE = "io.camunda.zeebe:userTask"
ACTIVATION_TIMEOUT_MS = 24 * 60 * 60 * 1000  # 24h lock per activation
MAX_JOBS_PER_ACTIVATION = 50
ACTIVATION_REQUEST_TIMEOUT_MS = 30_000  # long-poll window
WORKER_NAME = "kaisya-user-task-sink"

# Zeebe 8.6 writes these custom-header keys on userTask jobs:
HDR_ASSIGNEE = "io.camunda.zeebe:assignee"
HDR_CANDIDATE_GROUPS = "io.camunda.zeebe:candidateGroups"
HDR_CANDIDATE_USERS = "io.camunda.zeebe:candidateUsers"
HDR_DUE_DATE = "io.camunda.zeebe:dueDate"
HDR_FOLLOW_UP_DATE = "io.camunda.zeebe:followUpDate"
HDR_FORM_KEY = "io.camunda.zeebe:formKey"
HDR_USER_TASK_NAME = "io.camunda.zeebe:userTaskName"


# ---------------------------------------------------------------------------
# Activation payload
# ---------------------------------------------------------------------------


@dataclass
class ActivatedUserTask:
    job_key: int
    process_instance_key: int
    process_definition_key: int
    bpmn_process_id: str
    element_id: str
    element_name: str
    form_key: str | None
    candidate_groups: list[str]
    candidate_users: list[str]
    assignee: str | None
    due_date: str | None
    variables: dict[str, Any]


def _parse_maybe_json(value: Any) -> Any:
    """Zeebe stores some headers as JSON arrays (candidateGroups).
    Others are bare strings. Accept both."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("[") or s.startswith("{"):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return value
        return value
    return value


def _parse_activated(job: Any) -> ActivatedUserTask:
    """Convert a zeebe_grpc ActivatedJob into our dataclass."""
    headers = {}
    raw_headers = job.customHeaders or ""
    if raw_headers:
        try:
            headers = json.loads(raw_headers)
        except json.JSONDecodeError:
            headers = {}
    variables = {}
    raw_vars = job.variables or ""
    if raw_vars:
        try:
            variables = json.loads(raw_vars)
        except json.JSONDecodeError:
            variables = {}

    cg = _parse_maybe_json(headers.get(HDR_CANDIDATE_GROUPS)) or []
    cu = _parse_maybe_json(headers.get(HDR_CANDIDATE_USERS)) or []
    if isinstance(cg, str):
        cg = [cg]
    if isinstance(cu, str):
        cu = [cu]

    return ActivatedUserTask(
        job_key=int(job.key),
        process_instance_key=int(job.processInstanceKey),
        process_definition_key=int(job.processDefinitionKey),
        bpmn_process_id=str(job.bpmnProcessId or ""),
        element_id=str(job.elementId or ""),
        element_name=str(headers.get(HDR_USER_TASK_NAME) or job.elementId or ""),
        form_key=headers.get(HDR_FORM_KEY) or None,
        candidate_groups=[str(x) for x in cg],
        candidate_users=[str(x) for x in cu],
        assignee=headers.get(HDR_ASSIGNEE) or None,
        due_date=headers.get(HDR_DUE_DATE) or None,
        variables=variables,
    )


# ---------------------------------------------------------------------------
# Activation loop
# ---------------------------------------------------------------------------


async def run_user_task_sink_loop() -> None:
    """Deprecated broker activation loop.

    Human task creation now belongs to pod-side LangGraph/LangServer handlers.
    Keep the coroutine shape so old dispatcher startup hooks can call it
    without importing broker clients.
    """
    LOG.warning(
        "user_task_sink activation loop is deprecated; AgentGateway MCP is %s",
        AGENTGATEWAY_MCP_URL,
    )
    while True:
        await asyncio.sleep(3600)


# ---------------------------------------------------------------------------
# RW writes
# ---------------------------------------------------------------------------




def _upsert_human_task(job: ActivatedUserTask) -> None:
    """Blocking INSERT … ON CONFLICT … UPDATE into vertex_human_task."""
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat(timespec="seconds")
    created_date = now_utc.date().isoformat()
    description = (
        str(job.variables.get("caseTitle") or "")
        or str(job.variables.get("projectTitle") or "")
        or job.element_name
        or job.element_id
    )
    context_blob = json.dumps({
        "jobKey": job.job_key,
        "processInstanceKey": job.process_instance_key,
        "processDefinitionKey": job.process_definition_key,
        "bpmnProcessId": job.bpmn_process_id,
        "elementId": job.element_id,
        "elementName": job.element_name,
        "formKey": job.form_key,
        "candidateGroups": job.candidate_groups,
        "candidateUsers": job.candidate_users,
        "dueDate": job.due_date,
        "variables": job.variables,
    })
    get_kotoba_client().insert_row(
        "vertex_human_task",
        {
            "vertex_id": f"htask:zeebe:{job.job_key}",
            "_seq": job.job_key,
            "created_date": created_date,
            "sensitivity_ord": 1,
            "owner_did": "did:web:bpmn.etzhayyim.com",
            "task_code": f"zeebe:{job.job_key}",
            "title": job.element_name or job.element_id,
            "description": description,
            "task_type": f"bpmn:{job.element_id}",
            "assignee_did": job.assignee,
            "assignee_role": (job.candidate_groups or [None])[0],
            "deadline": (job.due_date[:10] if job.due_date else None),
            "related_project": str(job.process_instance_key),
            "status": "pending",
            "result_data": context_blob,
            "zeebe_job_key": job.job_key,
            "bpmn_process_instance_key": job.process_instance_key,
            "bpmn_process_definition_key": job.process_definition_key,
            "bpmn_process_id": job.bpmn_process_id,
            "bpmn_element_id": job.element_id,
            "form_key": job.form_key,
            "created_at": now_iso,
            "updated_at": now_iso,
        },
    )





def _mark_human_task_completed_sync(job_key: int, variables: dict[str, Any]) -> None:
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat(timespec="seconds")
    task_code_val = f"zeebe:{job_key}"

    # Fetch the existing task to get its vertex_id for upsert
    existing_task = get_kotoba_client().select_first_where(
        "vertex_human_task",
        "task_code",
        task_code_val,
        columns=["vertex_id", "created_date", "sensitivity_ord", "owner_did",
                 "task_code", "title", "description", "task_type",
                 "assignee_did", "assignee_role",
                 "priority", "deadline", "related_project",
                 "status", "result_data",
                 "zeebe_job_key", "bpmn_process_instance_key", "bpmn_process_definition_key",
                 "bpmn_process_id", "bpmn_element_id", "form_key",
                 "created_at", "updated_at"]
    )

    if existing_task:
        # Update existing task fields
        existing_task["status"] = "completed"
        existing_task["completed_at"] = now_iso
        existing_task["updated_at"] = now_iso
        existing_task["result"] = "complete"
        existing_task["result_data"] = json.dumps(variables)

        # Perform upsert using insert_row
        get_kotoba_client().insert_row("vertex_human_task", existing_task)
    else:
        LOG.warning("Could not find human task with task_code %s to mark as completed.", task_code_val)


# ---------------------------------------------------------------------------
# Completion (called from dispatcher /zeebe/complete-user-task)
# ---------------------------------------------------------------------------


async def _fail_job(stub: Any, job_key: int, reason: str) -> None:
    await stub.FailJob(gateway_pb2.FailJobRequest(
        jobKey=int(job_key),
        retries=0,
        errorMessage=reason[:512],
        retryBackOff=0,
    ))


async def complete_user_task(job_key: int, variables: dict[str, Any]) -> None:
    """Mark the portal row completed for the deprecated compatibility route."""
    await asyncio.to_thread(_mark_human_task_completed_sync, job_key, variables)


# ---------------------------------------------------------------------------
# aiohttp route — registered by dispatcher_main
# ---------------------------------------------------------------------------


async def http_complete_user_task(request: Any) -> Any:
    """POST /zeebe/complete-user-task  {jobKey, variables} → {ok}."""
    from aiohttp import web  # deferred import — dispatcher owns aiohttp

    try:
        body = await request.json()
    except Exception as e:  # noqa: BLE001
        return web.json_response({"error": f"invalid JSON: {e}"}, status=400)
    try:
        job_key = int(body.get("jobKey"))
    except (TypeError, ValueError):
        return web.json_response({"error": "jobKey required (int)"}, status=400)
    variables = body.get("variables") or {}
    if not isinstance(variables, dict):
        return web.json_response({"error": "variables must be object"}, status=400)

    try:
        await complete_user_task(job_key, variables)
    except Exception as e:  # noqa: BLE001
        LOG.exception("complete_user_task failed jobKey=%d: %s", job_key, e)
        return web.json_response(
            {"error": f"{type(e).__name__}: {str(e)[:300]}"},
            status=502,
        )
    return web.json_response({"ok": True, "jobKey": job_key})


def register_routes(app: Any) -> None:
    """Call from `dispatcher_main.make_app`:

        from kotodama.handlers.user_task_sink import (
            register_routes, run_user_task_sink_loop,
        )
        register_routes(app)
        app.on_startup.append(lambda a: a.__setitem__(
            "sink_task", asyncio.create_task(run_user_task_sink_loop()),
        ))
    """
    app.router.add_post("/zeebe/complete-user-task", http_complete_user_task)


# ---------------------------------------------------------------------------
# Readback helper (diagnostic / health)
# ---------------------------------------------------------------------------


def inbox_count() -> int:
    # R0: Multi-predicate count requires in-Python filtering.
    tasks = get_kotoba_client().select_where(
        "vertex_human_task",
        "owner_did",
        "did:web:bpmn.etzhayyim.com",
        columns=["status"]
    )
    count = sum(1 for task in tasks if task.get("status") == "pending")
    return count

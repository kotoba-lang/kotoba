"""LangServer start wrapper kept for older ingest imports."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


def _agentgateway_url() -> str:
    return os.environ.get(
        "AGENTGATEWAY_MCP_URL",
        "http://agentgateway-mcp.mitama-udf.svc.cluster.local:8080",
    ).rstrip("/")


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{_agentgateway_url()}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    if not body:
        return {}
    value = json.loads(body)
    return value if isinstance(value, dict) else {"result": value}


def start_process_if_configured(bpmn_process_id: str, variables: dict[str, Any]) -> tuple[str | None, str | None]:
    """Start a pod-side LangServer run via AgentGateway MCP.

    The function name remains for compatibility with existing ingest callers.
    BPMN IDs are now treated as run/tool IDs; BPMN XML is an audit contract,
    not an execution target.
    """
    if os.environ.get("INGEST_LANGSERVER_DISABLED") == "1":
        return None, "INGEST_LANGSERVER_DISABLED=1"
    try:
        response = _post_json(
            "/runs",
            {
                "assistant_id": bpmn_process_id,
                "input": variables,
                "metadata": {"runtimeKind": "k8s-langserver"},
            },
        )
        run_id = response.get("run_id") or response.get("id") or response.get("assistant_id")
        return str(run_id or f"langserver:{bpmn_process_id}:{int(time.time())}"), None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        return None, f"{type(e).__name__}: {str(e)[:300]}"

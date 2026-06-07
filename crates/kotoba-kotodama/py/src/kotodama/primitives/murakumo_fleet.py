"""Murakumo fleet health primitives for BPMN/LangServer.

The Cloudflare Worker remains the low-latency OpenAI-compatible edge gateway.
This module moves the scheduled fleet sampling work into Zeebe so K8s owns the
cron, retry, and worker execution lifecycle.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


MURAKUMO_DID = "did:web:murakumo.etzhayyim.com"
FLEET_COLLECTION = "com.etzhayyim.apps.murakumo.fleetHealth"
DEFAULT_LITELLM_URL = "http://litellm.murakumo-system.svc.cluster.local:4000"
HEALTH_TIMEOUT_SEC = 5.0

NODE_IP_MAP = {
    "192.168.1.61": "judah",
    "192.168.1.51": "benjamin",
    "192.168.1.49": "joseph",
    "192.168.1.60": "issachar",
    "192.168.1.59": "simeon",
    "192.168.1.52": "dan",
    "192.168.1.64": "naphtali",
    "192.168.1.65": "levi",
    "192.168.1.67": "zebulun",
    "192.168.1.54": "asher",
}
FLEET_NODES = list(NODE_IP_MAP.values())


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_node_name(api_base: str) -> str:
    for ip, name in NODE_IP_MAP.items():
        if ip in api_base:
            return name
    return "unknown"


def _get_json(url: str, headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT_SEC) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")[:500]
        return e.code, {"error": raw or e.reason}


def probe_litellm(litellm_url: str, bearer: str = "") -> dict[str, Any]:
    litellm_url = litellm_url.rstrip("/")
    headers = {"Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    start = time.monotonic()
    try:
        ready_status, ready = _get_json(f"{litellm_url}/health/readiness", headers)
        models_status, models = _get_json(f"{litellm_url}/v1/model/info", headers)
    except Exception as e:  # noqa: BLE001
        return {
            "reachable": False,
            "latencyMs": int((time.monotonic() - start) * 1000),
            "error": f"transport: {e}",
            "deployments": [],
        }

    latency_ms = int((time.monotonic() - start) * 1000)
    if ready_status != 200:
        return {
            "reachable": False,
            "latencyMs": latency_ms,
            "error": f"readiness http {ready_status}: {ready.get('error', '')}",
            "deployments": [],
        }
    if ready.get("status") != "healthy":
        return {
            "reachable": False,
            "latencyMs": latency_ms,
            "error": f"readiness status={ready.get('status')}",
            "version": ready.get("litellm_version"),
            "deployments": [],
        }
    deployments = models.get("data", []) if models_status == 200 else []
    return {
        "reachable": True,
        "latencyMs": latency_ms,
        "version": ready.get("litellm_version"),
        "deployments": deployments if isinstance(deployments, list) else [],
    }


def build_fleet_roster(probe: dict[str, Any]) -> dict[str, Any]:
    per_node: dict[str, dict[str, Any]] = {
        name: {"name": name, "ip": ip, "healthy": False}
        for ip, name in NODE_IP_MAP.items()
    }

    if probe.get("reachable"):
        seen_by_node: dict[str, list[str]] = {}
        for deployment in probe.get("deployments", []):
            if not isinstance(deployment, dict):
                continue
            params = deployment.get("litellm_params") or {}
            if not isinstance(params, dict):
                params = {}
            node_name = _extract_node_name(str(params.get("api_base") or ""))
            model = str(deployment.get("model_name") or params.get("model") or "")
            models = seen_by_node.setdefault(node_name, [])
            if model and model not in models:
                models.append(model)
            cur = per_node.get(node_name, {"name": node_name, "healthy": False})
            per_node[node_name] = {
                **cur,
                "healthy": True,
                "model": ",".join(models) or cur.get("model"),
            }

    nodes = [per_node[name] for name in FLEET_NODES]
    nodes.extend(v for k, v in per_node.items() if k not in FLEET_NODES)
    nodes_healthy = sum(1 for n in nodes if n.get("healthy"))
    nodes_total = len(nodes)
    now = _utc_now_iso()
    return {
        "$type": FLEET_COLLECTION,
        "v": 3,
        "ts": now,
        "epoch": int(time.time() * 1000),
        "healthPct": round((nodes_healthy / nodes_total) * 100) if nodes_total else 0,
        "nodesHealthy": nodes_healthy,
        "nodesTotal": nodes_total,
        "nodes": nodes,
        "litellm": {
            "reachable": bool(probe.get("reachable")),
            "latencyMs": probe.get("latencyMs"),
            "error": probe.get("error"),
            "version": probe.get("version"),
        },
    }


def write_fleet_health(roster: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    ts = str(roster.get("ts") or _utc_now_iso())
    rkey = "fleet-health-" + ts.replace("-", "").replace(":", "").replace(".", "")
    rkey = rkey.replace("T", "").replace("Z", "")
    uri = f"at://{MURAKUMO_DID}/{FLEET_COLLECTION}/{rkey}"
    litellm = roster.get("litellm") if isinstance(roster.get("litellm"), dict) else {}
    row = {
        "vertex_id": uri,
        "record_key": rkey,
        "status": "ok" if litellm.get("reachable") else "degraded",
        "value_json": json.dumps(roster, separators=(",", ":"), ensure_ascii=False),
        "indexed_at": ts,
        "created_at": ts,
        "updated_at": ts,
        "actor_did": MURAKUMO_DID,
        "org_did": "anon",
        "owner_did": MURAKUMO_DID,
        "sensitivity_ord": 2,
        "epoch_ms": int(roster.get("epoch") or 0),
        "health_pct": int(roster.get("healthPct") or 0),
        "nodes_healthy": int(roster.get("nodesHealthy") or 0),
        "nodes_total": int(roster.get("nodesTotal") or 0),
        "litellm_reachable": bool(litellm.get("reachable")),
        "litellm_latency_ms": int(litellm.get("latencyMs") or 0),
        "litellm_version": str(litellm.get("version") or ""),
        "litellm_error": str(litellm.get("error") or "")[:500],
    }
    get_kotoba_client().insert_row("vertex_murakumo_fleet_health", row)
    for node in roster.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_name = str(node.get("name") or "unknown")
        edge_id = f"edge:murakumo:fleet_node_health:{rkey}:{node_name}"
        edge_row_dict = {
            "edge_id": edge_id,
            "from_vertex_id": uri,
            "to_vertex_id": f"at://{MURAKUMO_DID}/com.etzhayyim.apps.murakumo.node/{node_name}",
            "node_name": node_name,
            "node_ip": str(node.get("ip") or ""),
            "healthy": bool(node.get("healthy")),
            "model": str(node.get("model") or ""),
            "snapshot_ts": ts,
            "created_at": ts,
            "owner_did": MURAKUMO_DID,
            "sensitivity_ord": 2,
        }
        get_kotoba_client().insert_row("edge_murakumo_fleet_node_health", edge_row_dict)
    return {"uri": uri, "rkey": rkey, "roster": roster}


def task_murakumo_fleet_health_check(
    litellmUrl: str = "",
    flush: bool = True,
) -> dict[str, Any]:
    url = litellmUrl or os.environ.get("LITELLM_URL") or DEFAULT_LITELLM_URL
    bearer = os.environ.get("LITELLM_MASTER") or os.environ.get("LITELLM_MASTER_KEY") or ""
    probe = probe_litellm(url, bearer)
    roster = build_fleet_roster(probe)
    out = write_fleet_health(roster, flush=flush)
    return {
        "ok": True,
        "uri": out["uri"],
        "healthPct": roster["healthPct"],
        "nodesHealthy": roster["nodesHealthy"],
        "nodesTotal": roster["nodesTotal"],
        "litellmReachable": roster["litellm"]["reachable"],
        "litellmLatencyMs": roster["litellm"]["latencyMs"],
        "litellmError": roster["litellm"]["error"],
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="murakumo.fleet.healthCheck",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_murakumo_fleet_health_check)

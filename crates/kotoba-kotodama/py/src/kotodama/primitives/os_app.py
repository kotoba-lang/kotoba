"""etzhayyim OS XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import json
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


OS_DID = "did:web:os.etzhayyim.com"
APP_ID = "os"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:8]}"


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v


def _transform_raw_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        raw = {k: _jsonable(v) for k, v in row.items()}
        props = raw.get("value_json") or raw.get("props")
        if isinstance(props, str) and props:
            try:
                parsed = json.loads(props)
                if isinstance(parsed, dict):
                    raw = {**parsed, **raw}
            except json.JSONDecodeError:
                pass
        aliases = {
            "vertex_id": "vertexId",
            "agent_id": "agentId",
            "app_id": "appId",
            "config_json": "config",
            "created_at": "createdAt",
            "updated_at": "updatedAt",
            "request_id": "requestId",
            "agent_did": "agentDid",
            "risk_tier": "riskTier",
            "estimated_cost": "estimatedCost",
            "context_json": "context",
            "expires_at": "expiresAt",
            "tags_json": "tags",
            "data_size": "dataSize",
            "window_id": "windowId",
            "content_type": "contentType",
            "content_url": "contentUrl",
        }
        for src, dst in aliases.items():
            if src in raw and dst not in raw:
                raw[dst] = raw[src]
        out.append(raw)
    return out


def _insert(collection: str, record: dict[str, Any], *, label: str = "", status: str = "") -> dict[str, Any]:
    record_kind = collection.rsplit(".", 1)[-1]
    rkey = str(record.get("agentId") or record.get("requestId") or record.get("windowId") or record.get("did") or _id("os"))[:64]
    now = str(record.get("created_at") or _now())
    vertex_id = f"at://{OS_DID}/{collection}/{rkey}"
    value = {**record, "vertexId": vertex_id, "rkey": rkey, "collection": collection, "label": label, "status": status or str(record.get("status") or "")}
    common = (str(record.get("org_id") or "anon"), str(record.get("user_id") or "anon"), str(record.get("actor_id") or APP_ID), OS_DID, 2)
    client = get_kotoba_client()
    if record_kind == "agent":
        client.insert_row(
            "vertex_os_agent",
            {
                "vertex_id": vertex_id,
                "agent_id": rkey,
                "did": str(record.get("did") or ""),
                "app_id": str(record.get("appId") or ""),
                "name": str(record.get("name") or label),
                "status": str(record.get("status") or status),
                "config_json": str(record.get("config") or "{}"),
                "created_at": now,
                "updated_at": str(record.get("updated_at") or now),
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
    elif record_kind == "agentEvent":
        client.insert_row(
            "vertex_os_agent_event",
            {
                "vertex_id": vertex_id,
                "agent_id": str(record.get("agentId") or ""),
                "event": str(record.get("event") or ""),
                "target": str(record.get("target") or ""),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
        client.insert_row(
            "edge_os_agent_event",
            {
                "edge_id": f"{OS_DID}:agent:{record.get('agentId')}:EVENT:{rkey}",
                "src_vid": f"at://{OS_DID}/com.etzhayyim.apps.os.agent/{record.get('agentId')}",
                "dst_vid": vertex_id,
                "agent_id": str(record.get("agentId") or ""),
                "relation": str(record.get("event") or "EVENT"),
                "created_at": now,
                "owner_did": OS_DID,
                "sensitivity_ord": 2,
            },
        )
    elif record_kind == "consentRequest":
        client.insert_row(
            "vertex_os_consent_request",
            {
                "vertex_id": vertex_id,
                "request_id": rkey,
                "agent_did": str(record.get("agentDid") or ""),
                "action": str(record.get("action") or ""),
                "risk_tier": str(record.get("riskTier") or ""),
                "estimated_cost": float(record.get("estimatedCost") or 0),
                "context_json": json.dumps(record.get("context"), ensure_ascii=False, default=str),
                "status": str(record.get("status") or status),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
    elif record_kind == "consentResponse":
        client.insert_row(
            "vertex_os_consent_response",
            {
                "vertex_id": vertex_id,
                "request_id": rkey,
                "verdict": str(record.get("verdict") or label),
                "reason": str(record.get("reason") or ""),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
        client.insert_row(
            "edge_os_consent_response",
            {
                "edge_id": f"{OS_DID}:consent:{rkey}:RESPONSE:{vertex_id}",
                "src_vid": f"at://{OS_DID}/com.etzhayyim.apps.os.consentRequest/{rkey}",
                "dst_vid": vertex_id,
                "request_id": rkey,
                "relation": "RESPONDED_BY",
                "created_at": now,
                "owner_did": OS_DID,
                "sensitivity_ord": 2,
            },
        )
    elif record_kind == "budgetAllocation":
        client.insert_row(
            "vertex_os_budget_allocation",
            {
                "vertex_id": vertex_id,
                "agent_id": str(record.get("agentId") or ""),
                "amount": float(record.get("amount") or 0),
                "expires_at": str(record.get("expiresAt") or ""),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
        client.insert_row(
            "edge_os_budget_agent",
            {
                "edge_id": f"{OS_DID}:budget:{rkey}:FOR:{record.get('agentId')}",
                "src_vid": vertex_id,
                "dst_vid": f"at://{OS_DID}/com.etzhayyim.apps.os.agent/{record.get('agentId')}",
                "agent_id": str(record.get("agentId") or ""),
                "relation": "ALLOCATED_TO",
                "created_at": now,
                "owner_did": OS_DID,
                "sensitivity_ord": 2,
            },
        )
    elif record_kind == "directoryEntry":
        client.insert_row(
            "vertex_os_directory_entry",
            {
                "vertex_id": vertex_id,
                "did": str(record.get("did") or ""),
                "name": str(record.get("name") or label),
                "tags_json": str(record.get("tags") or "[]"),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
    elif record_kind == "syncEvent":
        client.insert_row(
            "vertex_os_sync_event",
            {
                "vertex_id": vertex_id,
                "direction": str(record.get("direction") or ""),
                "path": str(record.get("path") or ""),
                "data_size": int(record.get("dataSize") or 0),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
    elif record_kind == "windowEvent":
        client.insert_row(
            "vertex_os_window_event",
            {
                "vertex_id": vertex_id,
                "window_id": rkey,
                "event": str(record.get("event") or ""),
                "app_id": str(record.get("appId") or ""),
                "title": str(record.get("title") or label),
                "content_type": str(record.get("contentType") or ""),
                "content_url": str(record.get("contentUrl") or ""),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
    elif record_kind == "auditEntry":
        client.insert_row(
            "vertex_os_audit_entry",
            {
                "vertex_id": vertex_id,
                "audit_id": rkey,
                "agent_id": str(record.get("agentId") or ""),
                "event": str(record.get("event") or ""),
                "target": str(record.get("target") or ""),
                "value_json": json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str),
                "created_at": now,
                "org_id": common[0],
                "user_id": common[1],
                "actor_id": common[2],
                "owner_did": common[3],
                "sensitivity_ord": common[4],
            },
        )
        client.insert_row(
            "edge_os_agent_audit_entry",
            {
                "edge_id": f"{OS_DID}:agent:{record.get('agentId')}:AUDIT:{rkey}",
                "src_vid": f"at://{OS_DID}/com.etzhayyim.apps.os.agent/{record.get('agentId')}",
                "dst_vid": vertex_id,
                "agent_id": str(record.get("agentId") or ""),
                "relation": str(record.get("event") or "AUDIT"),
                "created_at": now,
                "owner_did": OS_DID,
                "sensitivity_ord": 2,
            },
        )
        if False:
            pass
        else:
            raise ValueError(f"unsupported OS record kind: {record_kind}")
    return {"uri": vertex_id, "rkey": rkey}


def _list(collection: str, *, limit: int = 100) -> list[dict[str, Any]]:
    record_kind = collection.rsplit(".", 1)[-1]
    tables = {
        "agent": ("vertex_os_agent", "created_at"),
        "agentEvent": ("vertex_os_agent_event", "created_at"),
        "consentRequest": ("vertex_os_consent_request", "created_at"),
        "consentResponse": ("vertex_os_consent_response", "created_at"),
        "budgetAllocation": ("vertex_os_budget_allocation", "created_at"),
        "directoryEntry": ("vertex_os_directory_entry", "created_at"),
        "syncEvent": ("vertex_os_sync_event", "created_at"),
        "windowEvent": ("vertex_os_window_event", "created_at"),
        "auditEntry": ("vertex_os_audit_entry", "created_at"),
    }
    table, order_col = tables.get(record_kind, ("", "created_at"))
    if not table:
        return []
    client = get_kotoba_client()
    # R0: select_where does not support ORDER BY. Fetch more data and sort in Python.
    rows = client.select_where(table, "owner_did", OS_DID, limit=max(1, min(limit, 500)))
    # Sort in Python by the order_col and apply the limit
    sorted_rows = sorted(rows, key=lambda x: x.get(order_col, ""), reverse=True)
    return _transform_raw_data(sorted_rows)[:limit]


def _filter(collection: str, pred: Any, *, limit: int = 100) -> list[dict[str, Any]]:
    return [r for r in _list(collection, limit=500) if pred(r)][: max(0, limit)]


def task_os_agent_spawn(appId: str = "", name: str = "", config: Any = None, **_: Any) -> dict[str, Any]:
    agent_id = _id("agent")
    did = f"did:web:{appId}.etzhayyim.com" if appId else f"did:web:{agent_id}.etzhayyim.com"
    ts = _now()
    _insert("com.etzhayyim.apps.os.agent", {
        "agentId": agent_id, "did": did, "appId": appId, "name": name, "status": "active",
        "config": json.dumps(config if isinstance(config, dict) else {}, ensure_ascii=False),
        "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": ts, "updated_at": ts,
    }, label=name, status="active")
    return {"agentId": agent_id, "did": did, "status": "active"}


def _agent_event(agentId: str, event: str, **extra: Any) -> dict[str, Any]:
    _insert("com.etzhayyim.apps.os.agentEvent", {"agentId": agentId, "event": event, **extra, "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label=event)
    return {"agentId": agentId}


def task_os_agent_stop(agentId: str = "", **_: Any) -> dict[str, Any]:
    _agent_event(agentId, "stop")
    return {"agentId": agentId, "status": "stopped"}


def task_os_agent_pause(agentId: str = "", **_: Any) -> dict[str, Any]:
    _agent_event(agentId, "pause")
    return {"agentId": agentId, "status": "paused"}


def task_os_agent_resume(agentId: str = "", **_: Any) -> dict[str, Any]:
    _agent_event(agentId, "resume")
    return {"agentId": agentId, "status": "active"}


def task_os_agent_list(**_: Any) -> dict[str, Any]:
    return {"agents": _list("com.etzhayyim.apps.os.agent", limit=100)}


def task_os_agent_migrate(agentId: str = "", target: str = "", **_: Any) -> dict[str, Any]:
    _agent_event(agentId, "migrate", target=target)
    return {"agentId": agentId, "target": target, "status": "migrating"}


def task_os_consent_submit(agentDid: str = "", action: str = "", riskTier: str = "", estimatedCost: Any = 0, context: Any = None, **_: Any) -> dict[str, Any]:
    request_id = _id("consent")
    _insert("com.etzhayyim.apps.os.consentRequest", {
        "requestId": request_id, "agentDid": agentDid, "action": action, "riskTier": riskTier,
        "estimatedCost": estimatedCost, "context": context, "status": "pending",
        "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now(),
    }, label=action, status="pending")
    return {"requestId": request_id, "status": "pending"}


def task_os_consent_approve(requestId: str = "", **_: Any) -> dict[str, Any]:
    _insert("com.etzhayyim.apps.os.consentResponse", {"requestId": requestId, "verdict": "approved", "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label="approved")
    return {"requestId": requestId, "verdict": "approved"}


def task_os_consent_deny(requestId: str = "", reason: str = "", **_: Any) -> dict[str, Any]:
    _insert("com.etzhayyim.apps.os.consentResponse", {"requestId": requestId, "verdict": "denied", "reason": reason, "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label="denied")
    return {"requestId": requestId, "verdict": "denied"}


def task_os_consent_pending(**_: Any) -> dict[str, Any]:
    return {"pending": _filter("com.etzhayyim.apps.os.consentRequest", lambda r: r.get("status") == "pending", limit=50)}


def task_os_budget_allocate(agentId: str = "", amount: Any = 0, expiresAt: str = "", **_: Any) -> dict[str, Any]:
    _insert("com.etzhayyim.apps.os.budgetAllocation", {"agentId": agentId, "amount": amount, "expiresAt": expiresAt, "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label=agentId)
    return {"agentId": agentId, "allocated": amount}


def task_os_budget_balance(agentId: str = "", **_: Any) -> dict[str, Any]:
    rows = _filter("com.etzhayyim.apps.os.budgetAllocation", lambda r: str(r.get("agentId") or "") == agentId, limit=500)
    balance = sum(float(r.get("amount") or 0) for r in rows)
    return {"agentId": agentId, "balance": balance}


def task_os_directory_search(tags: Any = None, limit: Any = 50, **_: Any) -> dict[str, Any]:
    wanted = {str(t).strip() for t in tags} if isinstance(tags, list) else set()
    rows = _list("com.etzhayyim.apps.os.directoryEntry", limit=500)
    def match(row: dict[str, Any]) -> bool:
        if not wanted:
            return True
        raw = row.get("tags")
        parsed = json.loads(raw) if isinstance(raw, str) and raw.startswith("[") else raw
        vals = {str(v) for v in parsed} if isinstance(parsed, list) else set()
        return bool(vals & wanted)
    return {"agents": [r for r in rows if match(r)][: int(limit or 50)]}


def task_os_directory_register(did: str = "", name: str = "", tags: Any = None, **_: Any) -> dict[str, Any]:
    _insert("com.etzhayyim.apps.os.directoryEntry", {"did": did, "name": name, "tags": json.dumps(tags if isinstance(tags, list) else []), "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label=name)
    return {"did": did, "registered": True}


def task_os_audit_trail(agentId: str = "", limit: Any = 50, **_: Any) -> dict[str, Any]:
    rows = _filter("com.etzhayyim.apps.os.auditEntry", lambda r: str(r.get("agentId") or "") == agentId, limit=int(limit or 50))
    return {"trail": rows}


def task_os_sync_push(path: str = "", data: Any = "", **_: Any) -> dict[str, Any]:
    _insert("com.etzhayyim.apps.os.syncEvent", {"direction": "push", "path": path, "dataSize": len(str(data)), "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label=path)
    return {"path": path, "direction": "push", "status": "synced"}


def task_os_sync_pull(path: str = "", **_: Any) -> dict[str, Any]:
    rows = _filter("com.etzhayyim.apps.os.syncEvent", lambda r: r.get("path") == path and r.get("direction") == "push", limit=1)
    return {"path": path, "direction": "pull", "latest": rows[0] if rows else None}


def task_os_window_open(appId: str = "", title: str = "", contentType: str = "", contentUrl: str = "", **_: Any) -> dict[str, Any]:
    window_id = _id("win")
    _insert("com.etzhayyim.apps.os.windowEvent", {"windowId": window_id, "event": "open", "appId": appId, "title": title, "contentType": contentType, "contentUrl": contentUrl, "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label=title)
    return {"windowId": window_id, "status": "opened"}


def task_os_window_close(windowId: str = "", **_: Any) -> dict[str, Any]:
    _insert("com.etzhayyim.apps.os.windowEvent", {"windowId": windowId, "event": "close", "org_id": "anon", "user_id": "anon", "actor_id": APP_ID, "created_at": _now()}, label="close")
    return {"windowId": windowId, "status": "closed"}


def task_os_health(**_: Any) -> dict[str, Any]:
    return {"ok": True, "appId": APP_ID, "actorDID": OS_DID, "ts": _now()}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.os.agentList": task_os_agent_list,
        "xrpc.com.etzhayyim.apps.os.agentMigrate": task_os_agent_migrate,
        "xrpc.com.etzhayyim.apps.os.agentPause": task_os_agent_pause,
        "xrpc.com.etzhayyim.apps.os.agentResume": task_os_agent_resume,
        "xrpc.com.etzhayyim.apps.os.agentSpawn": task_os_agent_spawn,
        "xrpc.com.etzhayyim.apps.os.agentStop": task_os_agent_stop,
        "xrpc.com.etzhayyim.apps.os.auditTrail": task_os_audit_trail,
        "xrpc.com.etzhayyim.apps.os.budgetAllocate": task_os_budget_allocate,
        "xrpc.com.etzhayyim.apps.os.budgetBalance": task_os_budget_balance,
        "xrpc.com.etzhayyim.apps.os.consentApprove": task_os_consent_approve,
        "xrpc.com.etzhayyim.apps.os.consentDeny": task_os_consent_deny,
        "xrpc.com.etzhayyim.apps.os.consentPending": task_os_consent_pending,
        "xrpc.com.etzhayyim.apps.os.consentSubmit": task_os_consent_submit,
        "xrpc.com.etzhayyim.apps.os.directoryRegister": task_os_directory_register,
        "xrpc.com.etzhayyim.apps.os.directorySearch": task_os_directory_search,
        "xrpc.com.etzhayyim.apps.os.health": task_os_health,
        "xrpc.com.etzhayyim.apps.os.syncPull": task_os_sync_pull,
        "xrpc.com.etzhayyim.apps.os.syncPush": task_os_sync_push,
        "xrpc.com.etzhayyim.apps.os.windowClose": task_os_window_close,
        "xrpc.com.etzhayyim.apps.os.windowOpen": task_os_window_open,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)

"""Credits ledger handlers for BPMN + Zeebe."""

from __future__ import annotations

import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR = "did:web:credits.etzhayyim.com"

SPEND_COST = {
    "post": 100,
    "reply": 50,
    "dm": 50,
    "mcp_invoke": 50,
}
MCP_INVOKE_REQ_PER_KB = 10
MCP_INVOKE_RES_PER_KB = 10

HC_REWARD = {
    "hcTranslation": 300,
    "hcCodeReview": 500,
    "hcMicro": 200,
    "hcModeration": 100,
    "hcSurvey": 50,
}
COMPUTE_RATE_PER_JOB = 10
COMPUTE_RATE_PER_MIN = 30

SPEND_PUBLIC_FUND_BPS = 1000
SPEND_RATE_LIMIT_PER_HOUR = 60
EARN_RATE_LIMIT_PER_HOUR = 30
HIGH_VALUE_THRESHOLD = 5000
HC_MIN_APPROVAL_RATE = 50

PUBLIC_FUND_DESTINATIONS = [
    {
        "destinationId": "public-fund:common",
        "title": "Common Fund",
        "projectId": "etzhayyim-project-public-fund",
        "kind": "commonFund",
        "cofogCode": "00",
        "isDefault": True,
    },
    {
        "destinationId": "public-fund:education-family",
        "title": "Education & Family Fund",
        "projectId": "etzhayyim-project-public-fund",
        "kind": "campaign",
        "cofogCode": "09",
        "isDefault": False,
    },
    {
        "destinationId": "public-fund:health-access",
        "title": "Health Access Fund",
        "projectId": "etzhayyim-project-public-fund",
        "kind": "campaign",
        "cofogCode": "07",
        "isDefault": False,
    },
    {
        "destinationId": "public-fund:climate-resilience",
        "title": "Climate Resilience Fund",
        "projectId": "etzhayyim-project-public-fund",
        "kind": "campaign",
        "cofogCode": "05",
        "isDefault": False,
    },
]





def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _rkey(key: str) -> str:
    return "".join(c if c.isalnum() or c in "._~-" else "-" for c in key.lower())[:220] or "anon"


def _tx_id() -> str:
    return f"tx_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"





def _round_bps(amount: int, bps: int) -> int:
    return round((amount * bps) / 10_000)


def _compute_mcp_invoke_cost(req_bytes: int, res_bytes: int) -> int:
    req_kb = math.ceil(max(0, req_bytes) / 1024)
    res_kb = math.ceil(max(0, res_bytes) / 1024)
    return SPEND_COST["mcp_invoke"] + req_kb * MCP_INVOKE_REQ_PER_KB + res_kb * MCP_INVOKE_RES_PER_KB


def _resolve_spend_cost(action: str, *, amount: Any = None, reqBytes: Any = None, resBytes: Any = None, payloadBytes: Any = None, **_: Any) -> int:
    if amount is not None:
        cost = _int(amount)
        if cost >= 0:
            return cost
    if action == "mcp_invoke":
        return _compute_mcp_invoke_cost(_int(reqBytes if reqBytes is not None else payloadBytes), _int(resBytes))
    return SPEND_COST.get(action, 0)


def _find_destination(destination_id: str = "") -> dict[str, Any]:
    for item in PUBLIC_FUND_DESTINATIONS:
        if item["destinationId"] == destination_id:
            return dict(item)
    return dict(PUBLIC_FUND_DESTINATIONS[0])


def _spend_breakdown(amount: int) -> dict[str, int]:
    public_fund = _round_bps(amount, SPEND_PUBLIC_FUND_BPS)
    return {
        "spendAmount": amount,
        "serviceAmount": amount - public_fund,
        "publicFundAmount": public_fund,
        "publicFundBps": SPEND_PUBLIC_FUND_BPS,
    }


def _wallet(user_id: str) -> dict[str, Any] | None:
    return get_kotoba_client().select_first_where("vertex_credit_wallet", "user_id", user_id)


def _balance(user_id: str) -> int:
    row = _wallet(user_id)
    return _int((row or {}).get("balance"))


def _ensure_wallet(user_id: str) -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    get_kotoba_client().insert_row(
        "vertex_credit_wallet",
        {
            "vertex_id": f"{ACTOR}/wallet/{_rkey(user_id)}",
            "user_id": user_id,
            "balance": 0,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )


def _set_balance(user_id: str, balance: int) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    get_kotoba_client().insert_row(
        "vertex_credit_wallet",
        {
            "vertex_id": f"{ACTOR}/wallet/{_rkey(user_id)}",
            "balance": balance,
            "updated_at": now,
        },
    )


def _events_in_last_hour(user_id: str, event_type: str) -> int:
    cutoff = int(time.time() * 1000) - 3_600_000
    # R0: Multi-predicate COUNT using select_where with in-Python filtering over the kotoba Datom log
    events = get_kotoba_client().select_where("vertex_credits_af_event", "user_id", user_id, limit=2000)
    filtered_events = [e for e in events if e.get("event_type") == event_type and _int(e.get("ts_ms")) >= cutoff]
    return len(filtered_events)


def _check_rate_limit(user_id: str, event_type: str) -> dict[str, Any]:
    limit = EARN_RATE_LIMIT_PER_HOUR if event_type == "earn" else SPEND_RATE_LIMIT_PER_HOUR
    count = _events_in_last_hour(user_id, event_type)
    if count >= limit:
        return {"allowed": False, "reason": f"Rate limit exceeded: {count}/{limit} {event_type} events per hour"}
    return {"allowed": True}


def _record_af_event(user_id: str, event_type: str, amount: int) -> None:
    tx = _tx_id()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    get_kotoba_client().insert_row(
        "vertex_credits_af_event",
        {
            "vertex_id": f"{ACTOR}/af/{_rkey(user_id)}/{tx}",
            "user_id": user_id,
            "event_type": event_type,
            "amount": amount,
            "ts_ms": int(time.time() * 1000),
            "created_at": now,
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )


def _duplicate(source_ref: str) -> bool:
    if not source_ref:
        return False
    row = get_kotoba_client().select_first_where("vertex_credit_transaction", "source_ref", source_ref, columns=["vertex_id"])
    return row is not None


def _record_transaction(user_id: str, tx_type: str, amount: int, source: str, description: str, source_ref: str = "") -> str:
    tx = _tx_id()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    get_kotoba_client().insert_row(
        "vertex_credit_transaction",
        {
            "vertex_id": f"{ACTOR}/tx/{tx}",
            "tx_id": tx,
            "user_id": user_id,
            "tx_type": tx_type,
            "amount": amount,
            "source": source,
            "source_ref": source_ref,
            "description": description,
            "created_at": now,
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )
    return tx


def _allocation_preference(user_id: str, destination_id: str = "") -> dict[str, Any]:
    if destination_id:
        dest = _find_destination(destination_id)
    else:
        pref = get_kotoba_client().select_first_where("vertex_credit_allocation_preference", "user_id", user_id)
        dest = _find_destination(_str((pref or {}).get("destination_id")))
    return {
        "destinationId": dest["destinationId"],
        "title": dest["title"],
        "kind": dest["kind"],
        "projectId": dest["projectId"],
        "cofogCode": dest["cofogCode"],
        "allocationBps": SPEND_PUBLIC_FUND_BPS,
    }


def _record_public_fund_allocation(
    user_id: str,
    spend_tx_id: str,
    action: str,
    allocation: dict[str, int],
    preference: dict[str, Any],
    source_ref: str,
) -> None:
    allocation_id = _tx_id()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    get_kotoba_client().insert_row(
        "vertex_credits_public_fund_allocation",
        {
            "vertex_id": f"{ACTOR}/allocation/{allocation_id}",
            "allocation_id": allocation_id,
            "spend_tx_id": spend_tx_id,
            "user_id": user_id,
            "source_action": action,
            "source_ref": source_ref,
            "spend_amount": allocation["spendAmount"],
            "service_amount": allocation["serviceAmount"],
            "public_fund_amount": allocation["publicFundAmount"],
            "public_fund_bps": allocation["publicFundBps"],
            "destination_project_id": preference["projectId"],
            "destination_id": preference["destinationId"],
            "destination_title": preference["title"],
            "destination_kind": preference["kind"],
            "cofog_code": preference["cofogCode"],
            "created_at": now,
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )


def check_spend_allowed(userId: str = "", action: str = "", **kwargs: Any) -> dict[str, Any]:
    if not userId:
        return {"allowed": False, "reason": "userId is required", "balance": 0, "cost": 0}
    if not action:
        return {"allowed": False, "reason": "action is required", "balance": 0, "cost": 0}
    cost = _resolve_spend_cost(action, **kwargs)
    if cost <= 0:
        return {"allowed": False, "reason": f"unknown spend action: {action}", "balance": 0, "cost": 0}
    rate = _check_rate_limit(userId, "spend")
    if not rate["allowed"]:
        return {"allowed": False, "reason": rate["reason"], "balance": _balance(userId), "cost": cost}
    balance = _balance(userId)
    if balance < cost:
        return {"allowed": False, "reason": f"insufficient credits (balance {balance}, cost {cost})", "balance": balance, "cost": cost}
    return {"allowed": True, "balance": balance, "cost": cost}


def spend_credits(userId: str = "", action: str = "", toolNsid: str = "", actorDid: str = "", destinationId: str = "", sourceRef: str = "", **kwargs: Any) -> dict[str, Any]:
    if not userId:
        return {"error": "userId is required"}
    if not action:
        return {"error": "action is required"}
    cost = _resolve_spend_cost(action, **kwargs)
    if cost <= 0:
        return {"error": f"unknown spend action: {action}"}
    rate = _check_rate_limit(userId, "spend")
    if not rate["allowed"]:
        return {"error": rate["reason"]}
    _ensure_wallet(userId)
    balance = _balance(userId)
    if balance < cost:
        _record_spend_failure(userId, action, cost, balance, _str(toolNsid))
        return {"error": f"insufficient credits (balance {balance}, cost {cost})"}
    allocation = _spend_breakdown(cost)
    preference = _allocation_preference(userId, destinationId)
    source_ref = sourceRef or (f"mcp:{actorDid}:{toolNsid}" if action == "mcp_invoke" else f"{action}:{toolNsid}")
    if source_ref and _duplicate(source_ref):
        return {"error": f"Duplicate source: {source_ref}"}
    new_balance = balance - cost
    _set_balance(userId, new_balance)
    _record_af_event(userId, "spend", cost)
    tx = _record_transaction(
        userId,
        "spend",
        cost,
        "mcp" if action == "mcp_invoke" else action,
        f"{action} {toolNsid}; {allocation['publicFundAmount']} -> {preference['title']}",
        source_ref,
    )
    _record_public_fund_allocation(userId, tx, action, allocation, preference, source_ref)
    return {
        "balance": new_balance,
        "txId": tx,
        "amount": cost,
        "allocation": allocation,
        "destination": {
            "destinationId": preference["destinationId"],
            "title": preference["title"],
            "kind": preference["kind"],
            "projectId": preference["projectId"],
        },
    }


def _record_spend_failure(user_id: str, action: str, cost: int, balance: int, source_ref: str = "") -> None:
    fail_id = _tx_id()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    get_kotoba_client().insert_row(
        "vertex_credits_spend_failure",
        {
            "vertex_id": f"{ACTOR}/spend-failure/{fail_id}",
            "user_id": user_id,
            "action": action,
            "cost": cost,
            "balance": balance,
            "source_ref": source_ref,
            "created_at": now,
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )


def reward_from_compute(userId: str = "", sessionId: str = "", jobsDone: Any = 0, gpuTimeMs: Any = 0, amount: Any = None, source: str = "ameno", **_: Any) -> dict[str, Any]:
    if not userId:
        return {"error": "userId is required"}
    if not sessionId:
        return {"error": "sessionId is required"}
    gpu_minutes = int(_int(gpuTimeMs) / 60_000)
    reward = _int(amount) if amount is not None else (_int(jobsDone) * COMPUTE_RATE_PER_JOB + gpu_minutes * COMPUTE_RATE_PER_MIN)
    return _earn(userId, reward, f"{source}:{sessionId}", f"Compute reward: {_int(jobsDone)} jobs, {gpu_minutes} min GPU", f"compute:{sessionId}")


def reward_from_hc(userId: str = "", taskId: str = "", contributionType: str = "", amount: Any = None, approvalRate: Any = 100, **_: Any) -> dict[str, Any]:
    if not userId:
        return {"error": "userId is required"}
    if not taskId:
        return {"error": "taskId is required"}
    approval = _int(approvalRate, 100)
    if approval < HC_MIN_APPROVAL_RATE:
        return {"error": f"HC reputation gate: approvalRate {approval}% < {HC_MIN_APPROVAL_RATE}%"}
    reward = _int(amount) if amount is not None else HC_REWARD.get(contributionType, 100)
    return _earn(userId, reward, f"hc:{taskId}", f"HC {contributionType}: task {taskId} (approval {approval}%)", f"hc:{taskId}")


def _earn(user_id: str, amount: int, source: str, description: str, source_ref: str) -> dict[str, Any]:
    if amount <= 0:
        return {"error": "amount must be positive"}
    if amount > HIGH_VALUE_THRESHOLD:
        return {"error": f"High-value reward rejected: {amount}"}
    if _duplicate(source_ref):
        return {"error": f"Duplicate source: {source_ref}"}
    rate = _check_rate_limit(user_id, "earn")
    if not rate["allowed"]:
        return {"error": rate["reason"]}
    _ensure_wallet(user_id)
    balance = _balance(user_id)
    new_balance = balance + amount
    _set_balance(user_id, new_balance)
    _record_af_event(user_id, "earn", amount)
    tx = _record_transaction(user_id, "earn", amount, source, description, source_ref)
    return {"balance": new_balance, "txId": tx, "amount": amount}


def process_commit_spend(repo: str = "", collection: str = "", action: str = "", rkey: str = "", replyParent: str = "", **_: Any) -> dict[str, Any]:
    if not repo:
        return {"ok": False, "error": "repo is required"}
    if not action:
        if collection == "app.bsky.feed.post":
            action = "reply" if replyParent else "post"
        elif "convo" in collection and "message" in collection:
            action = "dm"
    if action not in SPEND_COST:
        return {"ok": True, "skipped": True, "reason": "no billable action"}
    source_ref = f"commit:{repo}:{rkey}"
    result = spend_credits(userId=repo, action=action, amount=SPEND_COST[action], toolNsid=source_ref, sourceRef=source_ref)
    return {"ok": "error" not in result, **result}


def heartbeat(**_: Any) -> dict[str, Any]:
    return {"ok": True, "actions": []}

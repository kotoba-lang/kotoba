"""Shiharai payment orchestration handlers for BPMN + Zeebe."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
import uuid
from typing import Any
from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR = "did:web:shiharai.etzhayyim.com"
APP = "shiharai"
APP_ACTOR_ID = "sys.shiharai"
APP_ORG = "etzhayyim"
APP_USER = "system"
APP_SENSITIVITY = 100
APPROVAL_MIN_LEN = 16


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() not in {"0", "false", "no", "off"}


def _gid(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:8]}"


def _rkey(value: str) -> str:
    return "".join(c if c.isalnum() or c in "._~-" else "-" for c in value.lower())[:220] or uuid.uuid4().hex





def _vertex(collection: str, rkey: str) -> str:
    return f"at://{ACTOR}/com.etzhayyim.apps.shiharai.{collection}/{_rkey(rkey)}"


def _normalize_issuer_to_handle(issuer: str) -> str:
    i = issuer.lower()
    if "東京都水道" in issuer or "tokyo.suidoapp" in i or "waterworks.metro.tokyo" in i:
        return "tokyo-waterworks"
    if "paypay" in i and "bank" in i:
        return "paypay-bank"
    if "bitflyer" in i:
        return "bitflyer"
    if "paidy" in i:
        return "paidy"
    if "nuro" in i:
        return "nuro"
    if "fly.io" in i or "flyio" in i or "fly-io" in i:
        return "flyio"
    if "stripe" in i:
        return "stripe"
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9-]+", "-", i))[:48] or "unknown"


def _bpmn_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    # ADR-2604282300: com.etzhayyim.* must NOT route through CF Workers — use K8s ClusterIP.
    base = (
        os.environ.get("BPMN_DISPATCHER_INTERNAL_URL")
        or os.environ.get("BPMN_URL")
        or os.environ.get("DISPATCHER_URL")
        or "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080"
    ).rstrip("/")
    req = urllib.request.Request(
        f"{base}/xrpc/com.etzhayyim.apps.bpmn.{method}",
        method="POST",
        data=json.dumps(params).encode(),
        headers={"content-type": "application/json", "user-agent": "etzhayyim-shiharai-zeebe/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return {"error": f"bpmn.{method} failed: {e.code}", "body": raw[:500]}
    except Exception as e:
        return {"error": f"bpmn.{method} failed: {e}"}


def _insert_bill(bill: dict[str, Any]) -> None:
    bill_vertex_id = _vertex("bill", bill["billId"])
    row_dict = {
        "vertex_id": bill_vertex_id,
        "created_date": today(),
        "sensitivity_ord": APP_SENSITIVITY,
        "owner_did": ACTOR,
        "rkey": bill["billId"],
        "repo": ACTOR,
        "bill_id": bill["billId"],
        "issuer": bill["issuer"],
        "biller_handle": bill["billerHandle"],
        "amount_jpy": bill["amountJpy"],
        "currency": "JPY",
        "due_date": bill["dueDate"],
        "customer_number": bill.get("customerNumber") or "",
        "invoice_number": bill.get("invoiceNumber") or "",
        "pay_url": bill.get("payUrl") or "",
        "method": bill.get("method") or "unknown",
        "source_email_id": bill.get("sourceEmailId") or "",
        "state": bill["state"],
        "extracted_at": bill["extractedAt"],
        "created_at": now_iso(),
        "org_id": APP_ORG,
        "user_id": APP_USER,
        "actor_id": APP_ACTOR_ID,
        "actor_did": ACTOR,
        "org_did": "anon",
    }
    get_kotoba_client().insert_row("vertex_shiharai_bill", row_dict)


def extract_bill(emailBody: str = "", emailSubject: str = "", emailFrom: str = "", sourceEmailId: str = "", **_: Any) -> dict[str, Any]:
    if not emailBody and not emailSubject:
        return {"error": "emailBody or emailSubject required"}
    issuer = emailFrom or emailSubject[:64]
    body = emailBody or ""
    amount_match = re.search(r"(?:￥|¥|JPY)\s*([0-9,]+)", body) or re.search(r"([0-9,]+)\s*円", body)
    due_match = re.search(r"(\d{4})[\/\-年](\d{1,2})[\/\-月](\d{1,2})", body)
    customer_match = re.search(r"お客様番号[::\s]*([A-Z0-9\-]+)", body)
    pay_url_match = re.search(r"https?://[^\s<>\"]+", body)
    bill_id = _gid("bill")
    bill = {
        "billId": bill_id,
        "issuer": issuer,
        "billerHandle": _normalize_issuer_to_handle(issuer),
        "amountJpy": _int(amount_match.group(1).replace(",", "")) if amount_match else 0,
        "dueDate": f"{due_match.group(1)}-{due_match.group(2).zfill(2)}-{due_match.group(3).zfill(2)}" if due_match else today(),
        "customerNumber": customer_match.group(1) if customer_match else "",
        "payUrl": pay_url_match.group(0) if pay_url_match else "",
        "method": "inferred-from-email" if amount_match else "unknown",
        "sourceEmailId": sourceEmailId,
        "state": "due",
        "extractedAt": now_iso(),
    }
    _insert_bill(bill)
    return {"billId": bill_id, "bill": bill, "vertexId": _vertex("bill", bill_id)}


def list_pending_bills(limit: Any = 50, billerHandle: str = "", includeOverdue: Any = True, **_: Any) -> dict[str, Any]:
    n = max(1, min(_int(limit, 50), 200))
    include = _bool(includeOverdue, True)
    states = ("due", "overdue") if include else ("due",)

    client = get_kotoba_client()

    # R0: Multi-predicate WHERE (state = ANY) and ORDER BY are handled in Python.
    # Fetch all bills that might match the criteria and then filter/order in Python.
    if billerHandle:
        all_bills = client.select_where("vertex_shiharai_bill", "biller_handle", billerHandle, limit=2000)
    else:
        # Assuming ACTOR is the owner of all bills if billerHandle is not specified.
        # This will fetch a broader set of bills, which are then filtered in Python.
        all_bills = client.select_where("vertex_shiharai_bill", "owner_did", ACTOR, limit=2000)

    filtered_bills = [
        bill for bill in all_bills
        if bill.get("state") in states
    ]

    # Apply order by
    # Handle cases where 'due_date' might be missing or not a comparable type
    rows = sorted(filtered_bills, key=lambda x: x.get("due_date", now_iso()))[:n] # Using now_iso() as a fallback for sorting

    # Select specific columns as per original SQL
    # The columns list is based on the original SQL query:
    # bill_id, issuer, biller_handle, amount_jpy, due_date, customer_number, pay_url, method, state
    rows = [{
        "bill_id": b.get("bill_id"),
        "issuer": b.get("issuer"),
        "biller_handle": b.get("biller_handle"),
        "amount_jpy": b.get("amount_jpy"),
        "due_date": b.get("due_date"),
        "customer_number": b.get("customer_number"),
        "pay_url": b.get("pay_url"),
        "method": b.get("method"),
        "state": b.get("state")
    } for b in rows]

    return {"limit": n, "billerHandle": billerHandle or None, "includeOverdue": include, "bills": rows}


def prepare_payment(
    billId: str = "",
    billerHandle: str = "",
    payUrl: str = "",
    expectedAmountJpy: Any = 0,
    method: str = "auto",
    requireConfirm: Any = True,
    processId: str = "",
    requesterDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    if not billId:
        return {"error": "billId required"}
    bill = get_kotoba_client().select_first_where("vertex_shiharai_bill", "bill_id", billId) or {}
    handle = billerHandle or _str(bill.get("biller_handle"))
    if not handle:
        return {"error": "billerHandle required"}
    url = payUrl or _str(bill.get("pay_url"))
    amount = _int(expectedAmountJpy) or _int(bill.get("amount_jpy"))
    pid = processId or f"shiharai-{handle}-v1"
    started = _bpmn_call(
        "startInstance",
        {
            "processId": pid,
            "variables": {"billId": billId, "billerHandle": handle, "payUrl": url, "expectedAmountJpy": amount, "method": method, "requireConfirm": _bool(requireConfirm), "requesterDid": requesterDid},
            "correlationKey": billId,
        },
    )
    if started.get("error"):
        return {"error": f"bpmn.startInstance: {started.get('error')}", "detail": started}
    instance_id = _str(started.get("instanceId"))
    job_id = f"job-{billId}"
    now = now_iso()
    job_vertex_id = _vertex("job", job_id)
    row_dict_job = {
        "vertex_id": job_vertex_id,
        "created_date": today(),
        "sensitivity_ord": APP_SENSITIVITY,
        "owner_did": ACTOR,
        "rkey": job_id,
        "repo": ACTOR,
        "job_id": job_id,
        "bill_id": billId,
        "biller_handle": handle,
        "method": method,
        "pay_url": url,
        "state": "active",
        "require_confirm": "true" if _bool(requireConfirm) else "false",
        "enqueued_at": now,
        "created_at": now,
        "org_id": APP_ORG,
        "user_id": APP_USER,
        "actor_id": APP_ACTOR_ID,
        "actor_did": ACTOR,
        "org_did": "anon",
    }
    get_kotoba_client().insert_row("vertex_shiharai_job", row_dict_job)
    return {"billId": billId, "jobId": job_id, "bpmnInstanceId": instance_id, "state": "active"}


def confirm_payment(jobId: str = "", billId: str = "", bpmnInstanceId: str = "", approvalToken: str = "", expectedAmountJpy: Any = 0, approvedByDid: str = "did:anonymous", **_: Any) -> dict[str, Any]:
    client = get_kotoba_client() # Get client instance once
    if not bpmnInstanceId and jobId:
        row = client.select_first_where("vertex_shiharai_job", "job_id", jobId)
        billId = billId or _str((row or {}).get("bill_id"))
    if not bpmnInstanceId and not billId:
        return {"error": "bpmnInstanceId, jobId or billId required"}
    if not approvalToken or len(approvalToken) < APPROVAL_MIN_LEN:
        return {"error": f"approvalToken required (>={APPROVAL_MIN_LEN} chars)"}
    token_hash = hashlib.sha256(approvalToken.encode()).hexdigest()
    signaled = _bpmn_call(
        "signalInstance",
        {"instanceId": bpmnInstanceId, "messageName": "approved", "payload": {"approvalTokenHash": token_hash, "approvedByDid": approvedByDid, "expectedAmountJpy": _int(expectedAmountJpy), "confirmedAt": now_iso()}},
    )
    if signaled.get("error"):
        return {"error": f"bpmn.signalInstance: {signaled.get('error')}", "detail": signaled}
    rid = bpmnInstanceId or jobId or billId
    payment_vertex_id = _vertex("payment", rid)
    row_dict_payment = {
        "vertex_id": payment_vertex_id,
        "created_date": today(),
        "sensitivity_ord": APP_SENSITIVITY,
        "owner_did": ACTOR,
        "rkey": rid,
        "repo": ACTOR,
        "payment_id": f"pay-{rid}",
        "bill_id": billId,
        "amount_jpy": _int(expectedAmountJpy),
        "approved_by_did": approvedByDid,
        "approval_token_hash": token_hash,
        "committed_at": now_iso(),
        "created_at": now_iso(),
        "org_id": APP_ORG,
        "user_id": APP_USER,
        "actor_id": APP_ACTOR_ID,
        "actor_did": ACTOR,
        "org_did": "anon",
    }
    client.insert_row("vertex_shiharai_payment", row_dict_payment)
    return {"jobId": jobId or None, "bpmnInstanceId": bpmnInstanceId or None, "billId": billId or None, "committed": False, "awaitingDaemonCommit": True}


def register_recurring(billerHandle: str = "", customerNumber: str = "", payMethod: str = "credit-card", requesterDid: str = "", **_: Any) -> dict[str, Any]:
    if not billerHandle or not customerNumber:
        return {"error": "billerHandle and customerNumber required"}
    recurring_id = _gid("recurring")
    started = _bpmn_call(
        "startInstance",
        {"processId": f"shiharai-{billerHandle}-recurring-v1", "variables": {"recurringId": recurring_id, "billerHandle": billerHandle, "customerNumber": customerNumber, "payMethod": payMethod, "requesterDid": requesterDid}, "correlationKey": recurring_id},
    )
    if started.get("error"):
        return {"error": f"bpmn.startInstance: {started.get('error')}", "detail": started}
    now = now_iso()
    recurring_vertex_id = _vertex("recurring", recurring_id)
    row_dict_recurring = {
        "vertex_id": recurring_vertex_id,
        "created_date": today(),
        "sensitivity_ord": APP_SENSITIVITY,
        "owner_did": ACTOR,
        "rkey": recurring_id,
        "repo": ACTOR,
        "recurring_id": recurring_id,
        "biller_handle": billerHandle,
        "customer_number": customerNumber,
        "pay_method": payMethod or "credit-card",
        "state": "pending",
        "registered_at": now,
        "created_at": now,
        "org_id": APP_ORG,
        "user_id": APP_USER,
        "actor_id": APP_ACTOR_ID,
        "actor_did": ACTOR,
        "org_did": "anon",
    }
    get_kotoba_client().insert_row("vertex_shiharai_recurring", row_dict_recurring)
    return {"recurringId": recurring_id, "bpmnInstanceId": _str(started.get("instanceId")), "state": "pending"}


def list_recurring(limit: Any = 50, **_: Any) -> dict[str, Any]:
    n = max(1, min(_int(limit, 50), 200))
    client = get_kotoba_client()

    # R0: ORDER BY registered_at DESC is handled in Python.
    # Fetch all recurring records for the actor (assuming owner_did is ACTOR, similar to other tables)
    # The client.select_where method requires a column and value to filter by.
    # We assume recurring records are owned by ACTOR.
    all_recurring = client.select_where("vertex_shiharai_recurring", "owner_did", ACTOR, limit=2000)

    # Apply order by and limit
    rows = sorted(all_recurring, key=lambda x: x.get("registered_at", now_iso()), reverse=True)[:n]

    # Select specific columns as per original SQL
    # recurring_id, biller_handle, customer_number, pay_method, state, registered_at
    rows = [{
        "recurring_id": r.get("recurring_id"),
        "biller_handle": r.get("biller_handle"),
        "customer_number": r.get("customer_number"),
        "pay_method": r.get("pay_method"),
        "state": r.get("state"),
        "registered_at": r.get("registered_at")
    } for r in rows]

    return {"recurring": rows, "limit": n}


def get_job_status(jobId: str = "", bpmnInstanceId: str = "", **_: Any) -> dict[str, Any]:
    if not jobId and not bpmnInstanceId:
        return {"error": "jobId or bpmnInstanceId required"}
    job = get_kotoba_client().select_first_where("vertex_shiharai_job", "job_id", jobId) if jobId else None
    state = _bpmn_call("getInstanceState", {"instanceId": bpmnInstanceId}) if bpmnInstanceId else {}
    return {"jobId": jobId or None, "bpmnInstanceId": bpmnInstanceId or None, "job": job or None, **state}

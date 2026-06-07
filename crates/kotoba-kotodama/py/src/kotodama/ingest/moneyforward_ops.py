"""MoneyForward replacement handlers for pod-side LangServer tasks.

The functions in this module are deliberately small SQL boundaries. Durable
retry and process state belong to LangGraph/Pregel orchestration; transactional
records live in the kotoba Datom log.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_MAP = {
    "works": "did:plc:etzhayyim-works",
    "japan": "did:plc:etzhayyim-japan",
    "labo": "did:plc:etzhayyim-labo",
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> str:
    return now_iso()[:10]


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_owner(value: Any) -> str:
    text = _str(value)
    if text.startswith("did:"):
        return text
    return OWNER_MAP.get(text, OWNER_MAP["works"])














# R0: _next_seq uses q() for MAX aggregate, derived Datomic attribute from table name.
def _next_seq(table: str) -> int:
    client = get_kotoba_client()
    # Convert SQL table name to Datomic-style keyword for attribute prefix
    # Example: "vertex_atrecord_seikyu_invoice" -> ":vertex-atrecord-seikyu-invoice/seq"
    datomic_attr_prefix = table.replace("_", "-")
    query_edn = f"""
    [:find (max ?s) .
     :where [?e :{datomic_attr_prefix}/seq ?s]]
    """
    result = client.q(query_edn)
    # result is list of lists, e.g., [[123]] for max value, or [[]] if no results
    max_seq = int(result[0][0]) if result and result[0] and result[0][0] is not None else 0
    return max_seq + 1


def _slug(text: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    return "-".join(part for part in out.split("-") if part)[:80] or "record"


def _vid(owner: str, nsid: str, rkey: str) -> str:
    return f"{owner}|{nsid}|{rkey}"


def _uri(owner: str, nsid: str, rkey: str) -> str:
    return f"at://{owner}/{nsid}/{rkey}"


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))


def _as_utc_ts(value: str, end_of_day: bool = False) -> str:
    date = (value or today())[:10]
    time_part = "23:59:59" if end_of_day else "00:00:00"
    return f"{date} {time_part}+00:00"


def issue_invoice(
    owner: str = "",
    customerDid: str = "",
    projectDid: str = "",
    agreementDid: str = "",
    invoiceNumber: str = "",
    period: Any = None,
    lineItems: Any = None,
    includeApprovedTimeEntries: Any = False,
    taxRate: Any = 0.10,
    discountAmount: Any = 0,
    currency: str = "JPY",
    issuedAt: str = "",
    dueAt: str = "",
    **_: Any,
) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not customerDid or not issuedAt or not dueAt:
        return {"error": "customerDid, issuedAt, dueAt required"}
    items = list(lineItems or [])
    owner_did = resolve_owner(owner)
    if not customerDid or not issuedAt or not dueAt:
        return {"error": "customerDid, issuedAt, dueAt required"}
    items = list(lineItems or [])
    attached = 0
    client = get_kotoba_client()
    if includeApprovedTimeEntries and projectDid:
        period_from = (period or {}).get("from") if isinstance(period, dict) else ""
        period_to = (period or {}).get("to") if isinstance(period, dict) else ""

        # R0: Multi-predicate WHERE and ORDER BY are applied in Python after broad fetch.
        time_entries = client.select_where(
            "vertex_atrecord_kousuu_time_entry",
            "project_did",
            projectDid,
            columns=["vertex_id", "member_did", "entry_date", "hours", "approval_status", "billable"],
            limit=2000
        )
        rows = []
        # Add necessary imports if not already present
        from datetime import datetime, timezone
        period_from_date = datetime.fromisoformat(period_from[:10]) if period_from else None
        period_to_date = datetime.fromisoformat(period_to[:10]) if period_to else None

        for entry in time_entries:
            if entry["approval_status"] == "approved" and entry["billable"]:
                entry_date_obj = datetime.fromisoformat(entry["entry_date"])
                if (period_from_date is None or entry_date_obj >= period_from_date) and \
                   (period_to_date is None or entry_date_obj <= period_to_date):
                    rows.append(entry)

        rows.sort(key=lambda x: x["entry_date"]) # Apply ORDER BY entry_date in Python

        for row in rows:
            items.append({
                "kind": "time",
                "description": f"Billable time {row['entry_date']} {row['member_did']}",
                "quantity": float(row.get("hours") or 0),
                "unitRate": 0,
                "amount": 0,
                "sourceDid": row["vertex_id"],
            })
        attached = len(rows)
    subtotal = sum(_float(item.get("amount")) for item in items) - _float(discountAmount)
    tax_rate = _float(taxRate, 0.10)
    tax_amount = round(subtotal * tax_rate)
    total = subtotal + tax_amount
    number = invoiceNumber or f"INV-{int(time.time())}"
    rkey = _slug(number)
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.seikyu.invoice", rkey)
    period_from = (period or {}).get("from", "")[:10] if isinstance(period, dict) else None
    period_to = (period or {}).get("to", "")[:10] if isinstance(period, dict) else None

    # Replicate _insert_if_missing logic
    existing_invoice = client.select_first_where("vertex_atrecord_seikyu_invoice", "vertex_id", vertex_id)
    inserted = 0
    if not existing_invoice:
        invoice_data = {
            "vertex_id": vertex_id,
            "_seq": _next_seq("vertex_atrecord_seikyu_invoice"),
            "owner_did": owner_did,
            "customer_did": customerDid,
            "project_did": projectDid or None,
            "agreement_did": agreementDid or None,
            "invoice_number": number,
            "period_from": period_from,
            "period_to": period_to,
            "issued_at": issuedAt,
            "due_at": dueAt,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": total,
            "currency": currency or "JPY",
            "status": "draft",
            "pdf_cid": None,
            "peppol_message_id": None,
            "sent_at": None,
            "paid_at": None,
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_seikyu_invoice", invoice_data)
        inserted = 1

    return {
        "invoiceDid": vertex_id,
        "uri": _uri(owner_did, "com.etzhayyim.apps.seikyu.invoice", rkey),
        "subtotal": subtotal,
        "taxAmount": tax_amount,
        "total": total,
        "status": "draft",
        "timeEntriesAttached": attached,
        "inserted": inserted > 0,
    }


def send_invoice(invoiceDid: str = "", pdfCid: str = "", peppolMessageId: str = "", **_: Any) -> dict[str, Any]:
    if not invoiceDid:
        return {"error": "invoiceDid required"}
    client = get_kotoba_client()
    existing_invoice = client.select_first_where("vertex_atrecord_seikyu_invoice", "vertex_id", invoiceDid)
    updated = 0
    if existing_invoice:
        existing_invoice["status"] = "sent"
        # COALESCE(NULLIF(%s,''), pdf_cid) logic
        existing_invoice["pdf_cid"] = pdfCid if pdfCid else existing_invoice.get("pdf_cid")
        existing_invoice["peppol_message_id"] = peppolMessageId if peppolMessageId else existing_invoice.get("peppol_message_id")
        existing_invoice["sent_at"] = now_iso()

        client.insert_row("vertex_atrecord_seikyu_invoice", existing_invoice)
        updated = 1
    return {"ok": updated > 0, "invoiceDid": invoiceDid, "status": "sent"}


def void_invoice(invoiceDid: str = "", reason: str = "", **_: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    existing_invoice = client.select_first_where("vertex_atrecord_seikyu_invoice", "vertex_id", invoiceDid)
    updated = 0
    if existing_invoice:
        existing_invoice["status"] = "void"
        # COALESCE(pdf_cid, %s) logic
        existing_invoice["pdf_cid"] = existing_invoice.get("pdf_cid") if existing_invoice.get("pdf_cid") else (reason or None)

        client.insert_row("vertex_atrecord_seikyu_invoice", existing_invoice)
        updated = 1
    return {"ok": updated > 0, "invoiceDid": invoiceDid, "status": "void"}


def record_payment_received(
    invoiceDid: str = "",
    paymentDate: str = "",
    amount: Any = 0,
    currency: str = "JPY",
    paymentMethod: str = "",
    reference: str = "",
    **_: Any,
) -> dict[str, Any]:
    client = get_kotoba_client()
    invoice = client.select_first_where("vertex_atrecord_seikyu_invoice", "vertex_id", invoiceDid, columns=["owner_did", "total"])
    if not invoice:
        return {"error": "invoice not found"}
    rkey = _slug(f"{invoiceDid}-{paymentDate or today()}-{reference or int(time.time())}")
    vertex_id = _vid(invoice["owner_did"], "com.etzhayyim.apps.seikyu.paymentReceived", rkey)

    # Replicate _insert_if_missing logic
    existing_payment = client.select_first_where("vertex_atrecord_seikyu_payment_received", "vertex_id", vertex_id)
    if not existing_payment:
        payment_data = {
            "vertex_id": vertex_id,
            "_seq": _next_seq("vertex_atrecord_seikyu_payment_received"),
            "owner_did": invoice["owner_did"],
            "invoice_did": invoiceDid,
            "payment_date": (paymentDate or today())[:10],
            "amount": _float(amount),
            "currency": currency or "JPY",
            "payment_method": paymentMethod or None,
            "reference": reference or None,
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_seikyu_payment_received", payment_data)

    # R0: SUM aggregate for paid amount uses q() as shims don't support SUM.
    query_edn = f"""
    [:find (sum ?amount) .
     :where
     [?e :vertex-atrecord-seikyu-payment-received/invoice-did "{invoiceDid}"]
     [?e :vertex-atrecord-seikyu-payment-received/amount ?amount]]
    """
    sum_result = client.q(query_edn)
    paid_amount = _float(sum_result[0][0]) if sum_result and sum_result[0] and sum_result[0][0] is not None else 0.0
    paid = {"paid": paid_amount} # Replicate the dict structure of original _fetch_one result

    status = "paid" if _float((paid or {}).get("paid")) >= _float(invoice.get("total")) else "partiallyPaid"

    # Replicate _execute UPDATE logic
    existing_invoice_to_update = client.select_first_where("vertex_atrecord_seikyu_invoice", "vertex_id", invoiceDid)
    if existing_invoice_to_update:
        existing_invoice_to_update["status"] = status
        if status == "paid":
            existing_invoice_to_update["paid_at"] = now_iso()
        client.insert_row("vertex_atrecord_seikyu_invoice", existing_invoice_to_update)

    return {"ok": True, "paymentDid": vertex_id, "invoiceDid": invoiceDid, "status": status}


def list_invoices(owner: str = "", status: str = "", customerDid: str = "", limit: Any = 100, **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    client = get_kotoba_client()

    # R0: Multiple WHERE clauses, ORDER BY, and LIMIT are applied in Python after a broad fetch.
    # Fetch all invoices for the owner_did
    all_invoices = client.select_where(
        "vertex_atrecord_seikyu_invoice",
        "owner_did",
        owner_did,
        limit=2000 # Max limit for broad fetch before Python filtering
    )

    filtered_invoices = []
    for invoice in all_invoices:
        if status and invoice.get("status") != status:
            continue
        if customerDid and invoice.get("customer_did") != customerDid:
            continue
        filtered_invoices.append(invoice)

    # Apply ORDER BY _seq DESC
    filtered_invoices.sort(key=lambda x: x.get("_seq", 0), reverse=True)

    # Apply LIMIT
    rows = filtered_invoices[:max(1, min(_int(limit, 100), 500))]

    return {"invoices": rows}


def get_invoice_aging(owner: str = "", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    client = get_kotoba_client()

    # R0: Replicating SQL VIEW 'view_seikyu_invoice_aging' logic with Datalog or Python.
    # Without the SQL definition of the view, this Datalog query is a placeholder.
    # It fetches all invoices for the owner, and any "aging" logic would be applied in Python.

    invoices = client.select_where(
        "vertex_atrecord_seikyu_invoice",
        "owner_did",
        owner_did,
        limit=2000 # R0: Limiting fetch for view simulation.
    )

    invoices.sort(key=lambda x: x.get("due_at", ""), reverse=False) # ORDER BY due_at ASC

    return {"owner": owner_did, "items": invoices}


def submit_peppol(invoiceDid: str = "", messageId: str = "", **_: Any) -> dict[str, Any]:
    msg = messageId or f"peppol-{int(time.time())}"
    client = get_kotoba_client()
    existing_invoice = client.select_first_where("vertex_atrecord_seikyu_invoice", "vertex_id", invoiceDid)
    updated = 0
    if existing_invoice:
        existing_invoice["peppol_message_id"] = msg
        client.insert_row("vertex_atrecord_seikyu_invoice", existing_invoice)
        updated = 1
    return {"ok": updated > 0, "invoiceDid": invoiceDid, "peppolMessageId": msg}


def draft_agreement(
    owner: str = "",
    counterpartyDid: str = "",
    title: str = "",
    agreementType: str = "other",
    effectiveFrom: str = "",
    termMonths: Any = None,
    autoRenew: Any = False,
    totalAmount: Any = None,
    currency: str = "JPY",
    recurringAmount: Any = None,
    recurringFrequency: str = "",
    pdfCid: str = "",
    **_: Any,
) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not counterpartyDid or not title or not effectiveFrom or not pdfCid:
        return {"error": "counterpartyDid, title, effectiveFrom, pdfCid required"}
    rkey = _slug(f"{title}-{int(time.time())}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.keiyaku.agreement", rkey)

    client = get_kotoba_client()
    existing_agreement = client.select_first_where("vertex_atrecord_keiyaku_agreement", "vertex_id", vertex_id)
    if not existing_agreement:
        agreement_data = {
            "vertex_id": vertex_id,
            "_seq": _next_seq("vertex_atrecord_keiyaku_agreement"),
            "owner_did": owner_did,
            "counterparty_did": counterpartyDid,
            "title": title,
            "agreement_type": agreementType,
            "effective_from": effectiveFrom[:10],
            "term_months": termMonths,
            "auto_renew": bool(autoRenew),
            "total_amount": totalAmount,
            "currency": currency or "JPY",
            "pdf_cid": pdfCid,
            "signing_status": "drafted",
            "signed_at": None,
            "terminated_at": None,
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_keiyaku_agreement", agreement_data)

    if recurringAmount:
        schedule_id = _vid(owner_did, "com.etzhayyim.apps.seikyu.recurringSchedule", _slug(rkey))
        existing_schedule = client.select_first_where("vertex_atrecord_seikyu_recurring_schedule", "vertex_id", schedule_id)
        if not existing_schedule:
            schedule_data = {
                "vertex_id": schedule_id,
                "_seq": _next_seq("vertex_atrecord_seikyu_recurring_schedule"),
                "owner_did": owner_did,
                "customer_did": counterpartyDid,
                "agreement_did": vertex_id,
                "amount": _float(recurringAmount),
                "currency": currency or "JPY",
                "frequency": recurringFrequency or "monthly",
                "next_issue_date": effectiveFrom[:10],
                "status": "active",
                "created_at": now_iso(),
            }
            client.insert_row("vertex_atrecord_seikyu_recurring_schedule", schedule_data)
    return {"agreementDid": vertex_id, "uri": _uri(owner_did, "com.etzhayyim.apps.keiyaku.agreement", rkey)}


def submit_for_signature(agreementDid: str = "", signerDid: str = "", **_: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    agreement = client.select_first_where("vertex_atrecord_keiyaku_agreement", "vertex_id", agreementDid, columns=["owner_did"])
    if not agreement:
        return {"error": "agreement not found"}
    flow_id = _vid(agreement["owner_did"], "com.etzhayyim.apps.keiyaku.signingFlow", _slug(f"{agreementDid}-{signerDid}-{int(time.time())}"))

    # Replicate _insert_if_missing logic
    existing_flow = client.select_first_where("vertex_atrecord_keiyaku_signing_flow", "vertex_id", flow_id)
    if not existing_flow:
        flow_data = {
            "vertex_id": flow_id,
            "_seq": _next_seq("vertex_atrecord_keiyaku_signing_flow"),
            "owner_did": agreement["owner_did"],
            "agreement_did": agreementDid,
            "signer_did": signerDid or None,
            "status": "requested",
            "requested_at": now_iso(),
            "completed_at": None,
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_keiyaku_signing_flow", flow_data)

    # Replicate _execute UPDATE logic
    existing_agreement_to_update = client.select_first_where("vertex_atrecord_keiyaku_agreement", "vertex_id", agreementDid)
    if existing_agreement_to_update:
        existing_agreement_to_update["signing_status"] = "sent"
        client.insert_row("vertex_atrecord_keiyaku_agreement", existing_agreement_to_update)

    return {"ok": True, "agreementDid": agreementDid, "signingFlowDid": flow_id, "status": "sent"}


def sign_agreement(agreementDid: str = "", signedAt: str = "", **_: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    ts = signedAt or now_iso()

    updated = 0
    # First UPDATE for agreement
    existing_agreement = client.select_first_where("vertex_atrecord_keiyaku_agreement", "vertex_id", agreementDid)
    if existing_agreement:
        existing_agreement["signing_status"] = "signed"
        existing_agreement["signed_at"] = ts
        client.insert_row("vertex_atrecord_keiyaku_agreement", existing_agreement)
        updated = 1

    # Second UPDATE for signing flow(s)
    # This assumes there might be multiple signing flows for one agreement.
    signing_flows = client.select_where("vertex_atrecord_keiyaku_signing_flow", "agreement_did", agreementDid)
    for flow in signing_flows:
        flow["status"] = "completed"
        flow["completed_at"] = ts
        client.insert_row("vertex_atrecord_keiyaku_signing_flow", flow) # Updates each flow by its vertex_id

    return {"ok": updated > 0, "agreementDid": agreementDid, "status": "signed"}


def void_agreement(agreementDid: str = "", reason: str = "", **_: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    updated = 0
    existing_agreement = client.select_first_where("vertex_atrecord_keiyaku_agreement", "vertex_id", agreementDid)
    if existing_agreement:
        existing_agreement["signing_status"] = "void"
        existing_agreement["terminated_at"] = now_iso()
        client.insert_row("vertex_atrecord_keiyaku_agreement", existing_agreement)
        updated = 1
    return {"ok": updated > 0, "agreementDid": agreementDid, "status": "void", "reason": reason}


def list_active_agreements(owner: str = "", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    client = get_kotoba_client()

    # R0: Replicating SQL VIEW 'view_keiyaku_active_agreements' logic with Datalog or Python.
    # Assuming 'view_keiyaku_active_agreements' selects from 'vertex_atrecord_keiyaku_agreement'
    # and filters for active agreements.

    # Fetch all agreements for the owner_did
    all_agreements = client.select_where(
        "vertex_atrecord_keiyaku_agreement",
        "owner_did",
        owner_did,
        limit=2000 # R0: Limiting fetch for view simulation.
    )

    # Filter for active agreements (assuming 'signing_status' != 'void' and 'terminated_at' is NULL)
    active_agreements = [
        agg for agg in all_agreements
        if agg.get("signing_status") != "void" and agg.get("terminated_at") is None
    ]

    # Apply ORDER BY effective_from DESC
    active_agreements.sort(key=lambda x: x.get("effective_from", ""), reverse=True)

    return {"owner": owner_did, "agreements": active_agreements}


def create_project(owner: str = "", customerDid: str = "", projectCode: str = "", projectName: str = "", budgetHours: Any = None, budgetCostJpy: Any = None, startDate: str = "", endDate: str = "", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not projectCode or not projectName or not startDate:
        return {"error": "projectCode, projectName, startDate required"}
    rkey = _slug(projectCode)
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.kousuu.project", rkey)

    client = get_kotoba_client()
    existing_project = client.select_first_where("vertex_atrecord_kousuu_project", "vertex_id", vertex_id)
    if not existing_project:
        project_data = {
            "vertex_id": vertex_id,
            "_seq": _next_seq("vertex_atrecord_kousuu_project"),
            "owner_did": owner_did,
            "customer_did": customerDid or None,
            "project_code": projectCode,
            "project_name": projectName,
            "budget_hours": budgetHours,
            "budget_cost_jpy": budgetCostJpy,
            "start_date": startDate[:10],
            "end_date": endDate[:10] if endDate else None,
            "status": "active",
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_kousuu_project", project_data)

    return {"projectDid": vertex_id, "uri": _uri(owner_did, "com.etzhayyim.apps.kousuu.project", rkey)}


def record_time_entry(owner: str = "", memberDid: str = "", projectDid: str = "", taskDid: str = "", entryDate: str = "", hours: Any = 0, billable: Any = True, **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not memberDid or not projectDid or not entryDate:
        return {"error": "memberDid, projectDid, entryDate required"}
    rkey = _slug(f"{memberDid}-{projectDid}-{entryDate}-{int(time.time() * 1000)}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.kousuu.timeEntry", rkey)

    client = get_kotoba_client()
    existing_time_entry = client.select_first_where("vertex_atrecord_kousuu_time_entry", "vertex_id", vertex_id)
    if not existing_time_entry:
        time_entry_data = {
            "vertex_id": vertex_id,
            "_seq": _next_seq("vertex_atrecord_kousuu_time_entry"),
            "owner_did": owner_did,
            "member_did": memberDid,
            "project_did": projectDid,
            "task_did": taskDid or None,
            "entry_date": entryDate[:10],
            "hours": _float(hours),
            "billable": bool(billable),
            "invoice_lineitem_cid": None,
            "approval_status": "submitted",
            "approved_by_did": None,
            "approved_at": None,
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_kousuu_time_entry", time_entry_data)

    return {"timeEntryDid": vertex_id, "uri": _uri(owner_did, "com.etzhayyim.apps.kousuu.timeEntry", rkey)}


def approve_time_entry(timeEntryDid: str = "", approvedByDid: str = "", approved: Any = True, **_: Any) -> dict[str, Any]:
    status = "approved" if bool(approved) else "rejected"
    client = get_kotoba_client()
    updated = 0
    existing_time_entry = client.select_first_where("vertex_atrecord_kousuu_time_entry", "vertex_id", timeEntryDid)
    if existing_time_entry:
        existing_time_entry["approval_status"] = status
        existing_time_entry["approved_by_did"] = approvedByDid or None
        existing_time_entry["approved_at"] = now_iso()
        client.insert_row("vertex_atrecord_kousuu_time_entry", existing_time_entry)
        updated = 1
    return {"ok": updated > 0, "timeEntryDid": timeEntryDid, "status": status}


def get_project_burn(owner: str = "", projectDid: str = "", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    client = get_kotoba_client()

    # R0: Replicating SQL VIEW 'view_kousuu_project_burn' logic with in-Python aggregation.
    # Fetches projects and time entries, then aggregates to simulate the view.

    projects = client.select_where(
        "vertex_atrecord_kousuu_project",
        "owner_did",
        owner_did,
        columns=["vertex_id", "project_code", "budget_hours", "budget_cost_jpy"],
        limit=2000
    )

    time_entries = client.select_where(
        "vertex_atrecord_kousuu_time_entry",
        "owner_did",
        owner_did,
        columns=["project_did", "entry_date", "hours"],
        limit=2000
    )

    project_map = {p["vertex_id"]: p for p in projects}

    burn_items = {} # Key: (project_did, period_month)

    for entry in time_entries:
        if projectDid and entry["project_did"] != projectDid:
            continue

        project = project_map.get(entry["project_did"])
        if not project:
            continue

        period_month = entry["entry_date"][:7] # YYYY-MM

        key = (entry["project_did"], period_month)
        if key not in burn_items:
            burn_items[key] = {
                "project_did": entry["project_did"],
                "project_code": project["project_code"],
                "period_month": period_month,
                "total_hours": 0.0,
                "total_cost_jpy": 0.0 # This would need more complex logic if the view calculated it.
            }

        burn_items[key]["total_hours"] += _float(entry["hours"])

    rows = list(burn_items.values())

    if projectDid:
        rows.sort(key=lambda x: x.get("period_month", "")) # ORDER BY period_month
    else:
        rows.sort(key=lambda x: (x.get("project_code", ""), x.get("period_month", ""))) # ORDER BY project_code, period_month

    return {"owner": owner_did, "projectDid": projectDid or None, "items": rows}


def submit_expense(owner: str = "", employeeDid: str = "", projectDid: str = "", vendorName: str = "", expenseDate: str = "", amount: Any = 0, currency: str = "JPY", taxRate: Any = 0, category: str = "", receiptCid: str = "", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not employeeDid or not expenseDate:
        return {"error": "employeeDid and expenseDate required"}
    rkey = _slug(f"{employeeDid}-{expenseDate}-{int(time.time() * 1000)}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.keihi.expense", rkey)

    client = get_kotoba_client()
    existing_expense = client.select_first_where("vertex_atrecord_keihi_expense", "vertex_id", vertex_id)
    if not existing_expense:
        expense_data = {
            "vertex_id": vertex_id,
            "_seq": _next_seq("vertex_atrecord_keihi_expense"),
            "owner_did": owner_did,
            "employee_did": employeeDid,
            "project_did": projectDid or None,
            "vendor_name": vendorName or None,
            "expense_date": expenseDate[:10],
            "amount": _float(amount),
            "currency": currency or "JPY",
            "tax_rate": _float(taxRate),
            "category": category or None,
            "receipt_cid": receiptCid or None,
            "status": "submitted",
            "approved_by_did": None,
            "approved_at": None,
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_keihi_expense", expense_data)

    return {"expenseDid": vertex_id, "uri": _uri(owner_did, "com.etzhayyim.apps.keihi.expense", rkey), "status": "submitted"}


def approve_expense(expenseDid: str = "", approved: Any = True, approvedByDid: str = "", reason: str = "", **_: Any) -> dict[str, Any]:
    status = "approved" if bool(approved) else "rejected"
    client = get_kotoba_client()
    updated = 0
    existing_expense = client.select_first_where("vertex_atrecord_keihi_expense", "vertex_id", expenseDid)
    if existing_expense:
        existing_expense["status"] = status
        existing_expense["approved_by_did"] = approvedByDid or None
        existing_expense["approved_at"] = now_iso()
        client.insert_row("vertex_atrecord_keihi_expense", existing_expense)
        updated = 1
    return {"ok": updated > 0, "expenseDid": expenseDid, "status": status, "reason": reason, "kaikeiSourceType": "com.etzhayyim.apps.keihi.expense.approved" if status == "approved" else ""}


def upsert_employee(owner: str = "", employeeDid: str = "", displayNameEncrypted: str = "", employmentStatus: str = "active", joinedOn: str = "", leftOn: str = "", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not employeeDid or not displayNameEncrypted:
        return {"error": "employeeDid and displayNameEncrypted required"}
    rkey = _slug(employeeDid)
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.jinji.employee", rkey)

    client = get_kotoba_client()

    employee_data = {
        "vertex_id": vertex_id,
        "_seq": _next_seq("vertex_atrecord_jinji_employee"), # _next_seq is called as per original DELETE+INSERT behavior
        "owner_did": owner_did,
        "employee_did": employeeDid,
        "display_name_encrypted": displayNameEncrypted,
        "employment_status": employmentStatus,
        "joined_on": joinedOn[:10] if joinedOn else None,
        "left_on": leftOn[:10] if leftOn else None,
        "created_at": now_iso(),
    }
    # insert_row handles upsert behavior, replacing both DELETE and INSERT
    client.insert_row("vertex_atrecord_jinji_employee", employee_data)

    return {"ok": True, "employeeVertexId": vertex_id}


def record_attendance(owner: str = "", employeeDid: str = "", workDate: str = "", minutesWorked: Any = 0, status: str = "submitted", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    rkey = _slug(f"{employeeDid}-{workDate}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.jinji.attendance", rkey)

    client = get_kotoba_client()
    existing_attendance = client.select_first_where("vertex_atrecord_jinji_attendance", "vertex_id", vertex_id)
    if not existing_attendance:
        attendance_data = {
            "vertex_id": vertex_id,
            "_seq": _next_seq("vertex_atrecord_jinji_attendance"),
            "owner_did": owner_did,
            "employee_did": employeeDid,
            "work_date": workDate[:10],
            "minutes_worked": _int(minutesWorked),
            "status": status or "submitted",
            "created_at": now_iso(),
        }
        client.insert_row("vertex_atrecord_jinji_attendance", attendance_data)

    return {"ok": True, "attendanceDid": vertex_id}


def complete_payroll_run(owner: str = "", payrollMonth: str = "", grossTotalEncrypted: str = "", statutoryTotalEncrypted: str = "", netTotalEncrypted: str = "", **_: Any) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not payrollMonth or not grossTotalEncrypted:
        return {"error": "payrollMonth and grossTotalEncrypted required"}
    rkey = _slug(payrollMonth)
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.jinji.payrollRun", rkey)

    client = get_kotoba_client()

    payroll_run_data = {
        "vertex_id": vertex_id,
        "_seq": _next_seq("vertex_atrecord_jinji_payroll_run"), # _next_seq is called as per original DELETE+INSERT behavior
        "owner_did": owner_did,
        "payroll_month": payrollMonth,
        "gross_total_encrypted": grossTotalEncrypted,
        "statutory_total_encrypted": statutoryTotalEncrypted or None,
        "net_total_encrypted": netTotalEncrypted or None,
        "status": "completed",
        "completed_at": now_iso(),
        "created_at": now_iso(),
    }
    # insert_row handles upsert behavior, replacing both DELETE and INSERT
    client.insert_row("vertex_atrecord_jinji_payroll_run", payroll_run_data)

    return {"ok": True, "payrollRunDid": vertex_id, "status": "completed", "kaikeiSourceType": "com.etzhayyim.apps.jinji.payrollRun.completed"}


def generate_statutory_report(
    owner: str = "",
    reportType: str = "",
    periodFrom: str = "",
    periodTo: str = "",
    artifactCid: str = "",
    **_: Any,
) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not reportType or not periodFrom or not periodTo:
        return {"error": "reportType, periodFrom, periodTo required"}
    rkey = _slug(f"{reportType}-{periodFrom[:10]}-{periodTo[:10]}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.kaikei.statutoryReport", rkey)

    client = get_kotoba_client()

    report_data = {
        "vertex_id": vertex_id,
        "_seq": _next_seq("vertex_kaikei_statutory_report"), # _next_seq is called as per original DELETE+INSERT behavior
        "owner_did": owner_did,
        "report_type": reportType,
        "period_from": periodFrom[:10],
        "period_to": periodTo[:10],
        "artifact_cid": artifactCid or None,
        "status": "generated",
        "generated_at": now_iso(),
        "created_at": now_iso(),
    }
    # insert_row handles upsert behavior, replacing both DELETE and INSERT
    client.insert_row("vertex_kaikei_statutory_report", report_data)

    return {"ok": True, "reportDid": vertex_id, "status": "generated"}


def validate_moneyforward_parity(
    owner: str = "",
    periodFrom: str = "",
    periodTo: str = "",
    mfExportCid: str = "",
    mfTotal: Any = 0,
    **_: Any,
) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not periodFrom or not periodTo:
        return {"error": "periodFrom and periodTo required"}
    client = get_kotoba_client()

    # R0: SUM aggregate with multiple WHERE clauses uses q() as shims don't support complex aggregates or multiple filters.
    query_edn = f"""
    [:find (sum ?amount) .
     :where
     [?e :vertex-atrecord-kaikei-journal-entry/owner-did "{owner_did}"]
     [?e :vertex-atrecord-kaikei-journal-entry/posted-at ?posted-at]
     [(.compareTo ?posted-at "{_as_utc_ts(periodFrom)}") ?comp_start]
     [(.compareTo ?posted-at "{_as_utc_ts(periodTo, end_of_day=True)}") ?comp_end]
     [(>= ?comp_start 0)]
     [(<= ?comp_end 0)]
     [?e :vertex-atrecord-kaikei-journal-entry/amount ?amount]]
    """
    sum_result = client.q(query_edn)
    rw_total = _float(sum_result[0][0]) if sum_result and sum_result[0] and sum_result[0][0] is not None else 0.0
    rw = {"total": rw_total}

    mf_total = _float(mfTotal, rw_total)
    diff = rw_total - mf_total
    status = "matched" if abs(diff) < 1 else "mismatch"
    rkey = _slug(f"{periodFrom[:10]}-{periodTo[:10]}-{int(time.time())}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.kaikei.moneyForwardParityRun", rkey)

    parity_run_data = {
        "vertex_id": vertex_id,
        "_seq": _next_seq("vertex_kaikei_moneyforward_parity_run"),
        "owner_did": owner_did,
        "period_from": periodFrom[:10],
        "period_to": periodTo[:10],
        "mf_export_cid": mfExportCid or None,
        "rw_total": rw_total,
        "mf_total": mf_total,
        "diff_amount": diff,
        "status": status,
        "checked_at": now_iso(),
        "created_at": now_iso(),
    }
    client.insert_row("vertex_kaikei_moneyforward_parity_run", parity_run_data)

    return {"ok": True, "parityRunDid": vertex_id, "status": status, "diffAmount": diff}


def register_saas_asset(
    owner: str = "",
    provider: str = "",
    assetType: str = "",
    externalId: str = "",
    displayName: str = "",
    assigneeDid: str = "",
    metadata: Any = None,
    status: str = "active",
    **_: Any,
) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not provider or not assetType or not externalId or not displayName:
        return {"error": "provider, assetType, externalId, displayName required"}
    rkey = _slug(f"{provider}-{assetType}-{externalId}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.kaisya.saasAsset", rkey)

    client = get_kotoba_client()

    asset_data = {
        "vertex_id": vertex_id,
        "_seq": _next_seq("vertex_kaisya_saas_asset"), # _next_seq is called as per original DELETE+INSERT behavior
        "owner_did": owner_did,
        "provider": provider,
        "asset_type": assetType,
        "external_id": externalId,
        "display_name": displayName,
        "assignee_did": assigneeDid or None,
        "metadata_json": _json(metadata),
        "status": status or "active",
        "observed_at": now_iso(),
        "created_at": now_iso(),
    }
    # insert_row handles upsert behavior, replacing both DELETE and INSERT
    client.insert_row("vertex_kaisya_saas_asset", asset_data)

    return {"ok": True, "assetDid": vertex_id}


def record_year_end_adjustment(
    owner: str = "",
    employeeDid: str = "",
    taxYear: Any = 0,
    declarationHash: str = "",
    artifactCid: str = "",
    status: str = "submitted",
    **_: Any,
) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not employeeDid or not taxYear or not declarationHash:
        return {"error": "employeeDid, taxYear, declarationHash required"}
    rkey = _slug(f"{employeeDid}-{taxYear}")
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.jinji.yearEndAdjustment", rkey)

    client = get_kotoba_client()
    done = now_iso() if status == "completed" else None

    adjustment_data = {
        "vertex_id": vertex_id,
        "_seq": _next_seq("vertex_atrecord_jinji_year_end_adjustment"), # _next_seq is called as per original DELETE+INSERT behavior
        "owner_did": owner_did,
        "employee_did": employeeDid,
        "tax_year": _int(taxYear),
        "declaration_hash": declarationHash,
        "status": status or "submitted",
        "artifact_cid": artifactCid or None,
        "completed_at": done,
        "created_at": now_iso(),
    }
    # insert_row handles upsert behavior, replacing both DELETE and INSERT
    client.insert_row("vertex_atrecord_jinji_year_end_adjustment", adjustment_data)

    return {"ok": True, "yearEndAdjustmentDid": vertex_id}


def register_mynumber_vault_ref(
    owner: str = "",
    employeeDid: str = "",
    vaultRefEncrypted: str = "",
    declarationHash: str = "",
    status: str = "active",
    **_: Any,
) -> dict[str, Any]:
    owner_did = resolve_owner(owner)
    if not employeeDid or not vaultRefEncrypted or not declarationHash:
        return {"error": "employeeDid, vaultRefEncrypted, declarationHash required"}
    rkey = _slug(employeeDid)
    vertex_id = _vid(owner_did, "com.etzhayyim.apps.jinji.mynumberVaultRef", rkey)

    client = get_kotoba_client()

    vault_ref_data = {
        "vertex_id": vertex_id,
        "_seq": _next_seq("vertex_atrecord_jinji_mynumber_vault_ref"), # _next_seq is called as per original DELETE+INSERT behavior
        "owner_did": owner_did,
        "employee_did": employeeDid,
        "vault_ref_encrypted": vaultRefEncrypted,
        "declaration_hash": declarationHash,
        "status": status or "active",
        "created_at": now_iso(),
    }
    # insert_row handles upsert behavior, replacing both DELETE and INSERT
    client.insert_row("vertex_atrecord_jinji_mynumber_vault_ref", vault_ref_data)

    return {"ok": True, "vaultRefDid": vertex_id}

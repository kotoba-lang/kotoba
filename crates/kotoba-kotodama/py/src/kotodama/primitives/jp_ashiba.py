"""jp-ashiba XRPC primitives for BPMN/LangServer.

Moves scaffold catalog/rental/subscription logic out of the Cloudflare AppView.
Write-side domain actions persist to concrete jp-ashiba graph vertices/edges.
Only visible status updates are emitted as social AT feed posts.
"""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import json
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.yoro_social import build_repo_record, insert_social_post_record


ASHIBA_DID = "did:web:jp-ashiba.etzhayyim.com"
ESTIMATOR_DID = "did:web:jp-ashiba.etzhayyim.com:actor:estimator"
SCHEDULER_DID = "did:web:jp-ashiba.etzhayyim.com:actor:scheduler"
INSPECTOR_DID = "did:web:jp-ashiba.etzhayyim.com:actor:inspector"

SUBSCRIPTION_TIERS = {
    "starter": {"monthlyFee": 80_000, "deliveries": 2, "label": "starter"},
    "standard": {"monthlyFee": 250_000, "deliveries": 8, "label": "standard"},
    "enterprise": {"monthlyFee": 0, "deliveries": -1, "label": "enterprise"},
}

DOMAIN_COLLECTIONS = {
    "com.etzhayyim.apps.jpAshiba.rentalContract": {
        "table": "vertex_jp_ashiba_rental_contract",
        "key": "contractId",
        "columns": {
            "contract_id": "contractId",
            "customer_did": "customerDid",
            "site_address": "siteAddress",
            "total_amount": "totalAmount",
            "deposit_amount": "depositAmount",
            "start_date": "startDate",
            "end_date": "endDate",
        },
    },
    "com.etzhayyim.apps.jpAshiba.subscriptionPlan": {
        "table": "vertex_jp_ashiba_subscription_plan",
        "key": "subscriptionId",
        "columns": {
            "subscription_id": "subscriptionId",
            "customer_did": "customerDid",
            "tier": "tier",
            "monthly_fee": "monthlyFee",
            "renewal_date": "renewalDate",
            "cancelled_at": "cancelledAt",
        },
    },
    "com.etzhayyim.apps.jpAshiba.siteSchedule": {
        "table": "vertex_jp_ashiba_site_schedule",
        "key": "scheduleId",
        "columns": {
            "schedule_id": "scheduleId",
            "contract_id": "contractId",
            "task_type": "taskType",
            "scheduled_date": "scheduledDate",
            "assigned_crew_did": "assignedCrewDid",
        },
    },
    "com.etzhayyim.apps.jpAshiba.inspectionRecord": {
        "table": "vertex_jp_ashiba_inspection",
        "key": "inspectionId",
        "columns": {
            "inspection_id": "inspectionId",
            "contract_id": "contractId",
            "item_id": "itemId",
            "inspector_did": "inspectorDid",
            "inspection_type": "inspectionType",
            "overall_result": "overallResult",
            "severity": "severity",
            "inspected_at": "inspectedAt",
        },
    },
}


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:8]}"


def _bounded_int(v: Any, default: int, *, min_value: int, max_value: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    return max(min_value, min(max_value, n))


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v


def _json_dumps(v: Any) -> str:
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False, default=str)


def _domain_vertex_id(collection: str, key: str) -> str:
    return f"at://{ASHIBA_DID}/{collection}/{key}"





def _write_social_post_record(repo: str, collection: str, record: dict[str, Any], *, rkey: str = "") -> dict[str, Any]:
    if collection != "app.bsky.feed.post":
        raise ValueError(f"social writer cannot persist non-post collection: {collection}")
    record = dict(record)
    record.setdefault("$type", collection)
    record.setdefault("createdAt", record.get("created_at") or _now())
    row = build_repo_record(repo=repo, collection=collection, record=record, rkey=rkey, actor_path="jp-ashiba")
    return insert_social_post_record(row, flush=False)


def _first_defect(record: dict[str, Any]) -> dict[str, Any]:
    defects = record.get("defects")
    if isinstance(defects, list) and defects and isinstance(defects[0], dict):
        return defects[0]
    return {}


def _with_derived_fields(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    if not out.get("itemId"):
        out["itemId"] = _first_defect(out).get("part") or ""
    if not out.get("severity"):
        out["severity"] = _first_defect(out).get("severity") or ""
    return out


def _write_domain_vertex(collection: str, record: dict[str, Any], *, rkey: str = "") -> dict[str, Any]:
    spec = DOMAIN_COLLECTIONS.get(collection)
    if not spec:
        raise ValueError(f"unsupported jp-ashiba domain collection: {collection}")
    record = _with_derived_fields({**record, "$type": collection})
    key = str(rkey or record.get(str(spec["key"])) or _id("rec"))
    now = str(record.get("created_at") or record.get("createdAt") or _now())
    vertex_id = _domain_vertex_id(collection, key)
    base = {
        "vertex_id": vertex_id,
        "vertex_key": key,
        "collection": collection,
        "status": (
            str(record.get("status") or record.get("overallResult"))
            if (record.get("status") or record.get("overallResult"))
            else None
        ),
        "value_json": _json_dumps(record),
        "created_at": now,
        "updated_at": str(record.get("updated_at") or record.get("updatedAt") or now),
        "org_id": str(record.get("org_id") or record.get("orgId") or "anon"),
        "user_id": str(record.get("user_id") or record.get("userId") or "anon"),
        "actor_id": str(record.get("actor_id") or record.get("actorId") or "actor:jp-ashiba"),
        "actor_did": str(record.get("actor_did") or ASHIBA_DID),
        "org_did": str(record.get("org_did") or record.get("orgId") or "anon"),
        "owner_did": ASHIBA_DID,
        "sensitivity_ord": 2,
    }
    promoted = {column: record.get(field) for column, field in dict(spec["columns"]).items()}
    table = str(spec["table"])
    columns = [*base.keys(), *promoted.keys()]
    placeholders = ",".join(["%s"] * len(columns))
    update_columns = [column for column in columns if column not in {"vertex_id", "created_at"}]
    update_sql = ", ".join(f"{column} = COALESCE(EXCLUDED.{column}, {table}.{column})" for column in update_columns)
    row_dict = {**base, **promoted}
    get_kotoba_client().insert_row(table, row_dict)
    _write_domain_edges(collection, key, vertex_id, record, now)
    return {"uri": vertex_id, "rkey": key}


def _write_edge(table: str, edge_key: str, src_vid: str, dst_vid: str, relation: str, record: dict[str, Any], now: str) -> None:
    edge_id = f"{table}:{edge_key}"
    row_dict = {
        "edge_id": edge_id,
        "edge_key": edge_key,
        "src_vid": src_vid,
        "dst_vid": dst_vid,
        "relation": relation,
        "value_json": _json_dumps(record),
        "created_at": now,
        "updated_at": now,
        "owner_did": ASHIBA_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row(table, row_dict)


def _write_domain_edges(collection: str, key: str, vertex_id: str, record: dict[str, Any], now: str) -> None:
    if collection == "com.etzhayyim.apps.jpAshiba.rentalContract" and record.get("customerDid"):
        customer = str(record["customerDid"])
        _write_edge("edge_jp_ashiba_customer_contract", f"{customer}:{key}", customer, vertex_id, "rents", record, now)
    elif collection == "com.etzhayyim.apps.jpAshiba.subscriptionPlan" and record.get("customerDid"):
        customer = str(record["customerDid"])
        _write_edge("edge_jp_ashiba_customer_subscription", f"{customer}:{key}", customer, vertex_id, "subscribes", record, now)
    elif collection == "com.etzhayyim.apps.jpAshiba.siteSchedule" and record.get("contractId"):
        contract_id = str(record["contractId"])
        src = _domain_vertex_id("com.etzhayyim.apps.jpAshiba.rentalContract", contract_id)
        _write_edge("edge_jp_ashiba_contract_schedule", f"{contract_id}:{key}", src, vertex_id, "scheduled", record, now)
    elif collection == "com.etzhayyim.apps.jpAshiba.inspectionRecord" and record.get("contractId"):
        contract_id = str(record["contractId"])
        src = _domain_vertex_id("com.etzhayyim.apps.jpAshiba.rentalContract", contract_id)
        _write_edge("edge_jp_ashiba_contract_inspection", f"{contract_id}:{key}", src, vertex_id, "inspected", record, now)


def _post(text: str, *, repo: str = ASHIBA_DID) -> dict[str, Any]:
    return _write_social_post_record(repo, "app.bsky.feed.post", {"text": text, "createdAt": _now()})


def _ctx_defaults(orgId: str = "", userId: str = "", **_: Any) -> tuple[str, str]:
    return orgId or "anon", userId or "anon"


def task_jp_ashiba_list_catalog(category: str = "", offset: Any = 0, limit: Any = 50, **_: Any) -> dict[str, Any]:
    limit_n = _bounded_int(limit, 50, min_value=1, max_value=200)
    offset_n = _bounded_int(offset, 0, min_value=0, max_value=100_000)
    clauses: list[str] = []
    params: list[Any] = []
    if category:
        clauses.append('"category" = %s')
        params.append(category)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    client = get_kotoba_client()
    if category:
        all_items = client.select_where("vertex_ScaffoldItem", "category", category)
    else:
        # R0: No direct way to select_all without a specific predicate, using q and filtering in Python for offset/limit.
        all_items_raw = client.q('[:find (pull ?e [*]) :where [?e :vertex_ScaffoldItem/vertex_id _]]')
        all_items = [item[0] for item in all_items_raw]

    items = all_items[offset_n : offset_n + limit_n]

    # For total, use q for aggregation as aggregate_where only supports count.
    # R0: Aggregation of sum(cnt) from mv_scaffold_item_count_by_category using q.
    if category:
        query_edn_total = f"""
        [:find (sum ?cnt) .
         :in $category
         :where
         [?e :mv_scaffold_item_count_by_category/vertex_id _]
         [?e :mv_scaffold_item_count_by_category/cnt ?cnt]
         [?e :mv_scaffold_item_count_by_category/category $category]
        ]
        """
        total_raw = client.q(query_edn_total, args=[category])
    else:
        query_edn_total = f"""
        [:find (sum ?cnt) .
         :where
         [?e :mv_scaffold_item_count_by_category/vertex_id _]
         [?e :mv_scaffold_item_count_by_category/cnt ?cnt]
        ]
        """
        total_raw = client.q(query_edn_total)

    total = int(total_raw or 0)
    return {"items": items, "offset": offset_n, "limit": limit_n, "total": total}


def task_jp_ashiba_get_item(itemId: str = "", **_: Any) -> dict[str, Any]:
    if not itemId:
        return {"error": "itemId required"}
    client = get_kotoba_client()
    row = client.select_first_where("vertex_ScaffoldItem", "itemId", itemId)
    return row if row else {"error": "not_found"}


def task_jp_ashiba_check_availability(
    category: str = "", quantity: Any = 1, startDate: str = "", endDate: str = "", **_: Any
) -> dict[str, Any]:
    qty = _bounded_int(quantity, 1, min_value=1, max_value=100_000)
    client = get_kotoba_client()
    qty = _bounded_int(quantity, 1, min_value=1, max_value=100_000)

    # R0: Multiple predicates and comparison (availableStock >= qty) handled in Datalog. LIMIT 20 applied in Python.
    query_edn = f"""
    [:find (pull ?e ["itemId" "spec" "availableStock" "unitPrice"])
     :in $category $condition
     :where
     [?e :vertex_ScaffoldItem/category $category]
     [?e :vertex_ScaffoldItem/condition $condition]
     [?e :vertex_ScaffoldItem/availableStock ?availableStock]
     [(>= ?availableStock {qty})]
    ]
    """
    items_raw = client.q(query_edn, args=[category, "good"])
    items = [item[0] for item in items_raw][:20] # Apply LIMIT 20 in Python
    return {"available": bool(items), "items": items, "requestedPeriod": {"startDate": startDate, "endDate": endDate}}
    return {"available": bool(items), "items": items, "requestedPeriod": {"startDate": startDate, "endDate": endDate}}


def task_jp_ashiba_create_quote(
    customerDid: str = "", siteAddress: str = "", siteGeo: Any = None, items: Any = None, orgId: str = "", userId: str = "", **_: Any
) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    quote_items: list[dict[str, Any]] = []
    total_amount = 0.0
    client = get_kotoba_client()
    for item in items if isinstance(items, list) else []:
        item_id = str(item.get("itemId") or "")
        qty = _num(item.get("quantity"))
        days = _num(item.get("days"))
        row = client.select_first_where("vertex_ScaffoldItem", "itemId", item_id, columns=["unitPrice", "availableStock"])
        if not row:
            continue
        unit_price = _num(row.get("unitPrice"))
        line_total = unit_price * qty * days
        total_amount += line_total
        quote_items.append({**item, "unitPrice": unit_price, "lineTotal": line_total})
    contract_id = _id("rc")
    deposit_amount = int(total_amount * 0.1)
    now = _now()
    _write_domain_vertex(
        "com.etzhayyim.apps.jpAshiba.rentalContract",
        {
            "contractId": contract_id,
            "customerDid": customerDid,
            "siteAddress": siteAddress,
            "siteGeo": siteGeo or {},
            "items": quote_items,
            "status": "quote",
            "totalAmount": int(total_amount),
            "depositAmount": deposit_amount,
            "org_id": org_id,
            "user_id": user_id,
            "actor_id": "actor:estimator",
            "created_at": now,
        },
        rkey=contract_id,
    )
    _post(f"Quote created: {siteAddress} - {len(quote_items)} items, total JPY {int(total_amount)}", repo=ESTIMATOR_DID)
    return {"contractId": contract_id, "status": "quote", "items": quote_items, "totalAmount": int(total_amount), "depositAmount": deposit_amount}


def task_jp_ashiba_confirm_rental(contractId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    now = _now()
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.rentalContract", {
        "contractId": contractId, "status": "confirmed", "confirmedAt": now,
        "org_id": org_id, "user_id": user_id, "actor_id": user_id, "created_at": now,
    }, rkey=contractId)
    _post(f"Rental confirmed: {contractId}")
    return {"contractId": contractId, "status": "confirmed"}


def task_jp_ashiba_extend_rental(contractId: str = "", newEndDate: str = "", additionalDays: Any = 0, orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.rentalContract", {
        "contractId": contractId, "status": "inUse", "endDate": newEndDate, "extensionDays": additionalDays,
        "org_id": org_id, "user_id": user_id, "actor_id": user_id, "created_at": _now(),
    }, rkey=contractId)
    return {"contractId": contractId, "newEndDate": newEndDate, "status": "extended"}


def task_jp_ashiba_return_rental(contractId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    now = _now()
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.rentalContract", {
        "contractId": contractId, "status": "dismantling", "returnRequestedAt": now,
        "org_id": org_id, "user_id": user_id, "actor_id": user_id, "created_at": now,
    }, rkey=contractId)
    _post(f"Return and dismantling started: contract {contractId}", repo=SCHEDULER_DID)
    return {"contractId": contractId, "status": "dismantling"}


def task_jp_ashiba_subscribe(customerDid: str = "", tier: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    tier_def = SUBSCRIPTION_TIERS.get(tier)
    if not tier_def:
        return {"error": "invalid_tier"}
    org_id, user_id = _ctx_defaults(orgId, userId)
    now_dt = _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0)
    renewal = now_dt + _dt.timedelta(days=30)
    subscription_id = _id("sub")
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.subscriptionPlan", {
        "subscriptionId": subscription_id, "customerDid": customerDid, "tier": tier,
        "monthlyFee": tier_def["monthlyFee"], "status": "active", "renewalDate": renewal.isoformat().replace("+00:00", "Z"),
        "org_id": org_id, "user_id": user_id, "actor_id": user_id, "created_at": now_dt.isoformat().replace("+00:00", "Z"),
    }, rkey=subscription_id)
    _post(f"New scaffold subscription: {tier_def['label']} JPY {tier_def['monthlyFee']} per month")
    return {"subscriptionId": subscription_id, "tier": tier, "monthlyFee": tier_def["monthlyFee"], "status": "active"}


def task_jp_ashiba_change_tier(subscriptionId: str = "", newTier: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    tier_def = SUBSCRIPTION_TIERS.get(newTier)
    if not tier_def:
        return {"error": "invalid_tier"}
    org_id, user_id = _ctx_defaults(orgId, userId)
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.subscriptionPlan", {
        "subscriptionId": subscriptionId, "tier": newTier, "monthlyFee": tier_def["monthlyFee"],
        "changedAt": _now(), "org_id": org_id, "user_id": user_id, "actor_id": user_id, "created_at": _now(),
    }, rkey=subscriptionId)
    return {"subscriptionId": subscriptionId, "newTier": newTier, "monthlyFee": tier_def["monthlyFee"]}


def task_jp_ashiba_cancel_subscription(subscriptionId: str = "", reason: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    now = _now()
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.subscriptionPlan", {
        "subscriptionId": subscriptionId, "status": "cancelled", "cancellationReason": reason,
        "cancelledAt": now, "org_id": org_id, "user_id": user_id, "actor_id": user_id, "created_at": now,
    }, rkey=subscriptionId)
    return {"subscriptionId": subscriptionId, "status": "cancelled"}


def task_jp_ashiba_get_usage_summary(subscriptionId: str = "", **_: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    subs = client.select_first_where("vertex_jp_ashiba_subscription_plan", "subscription_id", subscriptionId)
    if not subs:
        return {"error": "not_found"}

    customer_did = subs.get("customer_did")
    if not customer_did: # Should not happen if subs is valid, but good to check.
        return {"error": "customer_did not found for subscription"}

    # R0: Multiple predicates (customer_did AND status) handled in Datalog. LIMIT 100 applied in Python.
    query_edn_contracts = f"""
    [:find (pull ?e ["contract_id" "value_json" "start_date" "end_date"])
     :in $customer_did $status
     :where
     [?e :vertex_jp_ashiba_rental_contract/customer_did $customer_did]
     [?e :vertex_jp_ashiba_rental_contract/status $status]
    ]
    """
    contracts_raw = client.q(query_edn_contracts, args=[customer_did, "inUse"])
    contracts = [contract[0] for contract in contracts_raw][:100] # Apply LIMIT 100 in Python

    return {"subscription": subs, "activeRentals": contracts, "activeCount": len(contracts)}


def task_jp_ashiba_schedule_delivery(contractId: str = "", taskType: str = "", scheduledDate: str = "", assignedCrewDid: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    schedule_id = _id("sch")
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.siteSchedule", {
        "scheduleId": schedule_id, "contractId": contractId, "taskType": taskType, "scheduledDate": scheduledDate,
        "assignedCrewDid": assignedCrewDid, "status": "scheduled", "org_id": org_id, "user_id": user_id,
        "actor_id": "actor:scheduler", "created_at": _now(),
    }, rkey=schedule_id)
    _post(f"{taskType or 'task'} scheduled: {scheduledDate} - contract {contractId}", repo=SCHEDULER_DID)
    return {"scheduleId": schedule_id, "status": "scheduled"}


def task_jp_ashiba_record_inspection(contractId: str = "", inspectionType: str = "", checklist: Any = None, overallResult: str = "", defects: Any = None, orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    inspection_id = _id("ins")
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.inspectionRecord", {
        "inspectionId": inspection_id, "contractId": contractId, "inspectorDid": user_id,
        "inspectionType": inspectionType, "checklist": checklist or {}, "overallResult": overallResult,
        "defects": defects if isinstance(defects, list) else [], "inspectedAt": _now(),
        "org_id": org_id, "user_id": user_id, "actor_id": "actor:inspector", "created_at": _now(),
    }, rkey=inspection_id)
    if overallResult == "fail":
        _post(f"Safety inspection failed: contract {contractId} - {inspectionType}", repo=INSPECTOR_DID)
    return {"inspectionId": inspection_id, "overallResult": overallResult}


def task_jp_ashiba_report_defect(itemId: str = "", severity: str = "", description: str = "", photoCid: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    org_id, user_id = _ctx_defaults(orgId, userId)
    inspection_id = _id("def")
    _write_domain_vertex("com.etzhayyim.apps.jpAshiba.inspectionRecord", {
        "inspectionId": inspection_id, "itemId": itemId, "severity": severity, "inspectionType": "defect",
        "defects": [{"part": itemId, "severity": severity, "description": description, "photo_cid": photoCid}],
        "overallResult": "fail" if severity == "critical" else "conditionalPass",
        "inspectedAt": _now(), "org_id": org_id, "user_id": user_id, "actor_id": "actor:inspector", "created_at": _now(),
    }, rkey=inspection_id)
    if severity == "critical":
        _post(f"Critical scaffold defect: item {itemId} - {description}", repo=INSPECTOR_DID)
    return {"itemId": itemId, "severity": severity, "status": "reported"}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.jpAshiba.cancelSubscription": task_jp_ashiba_cancel_subscription,
        "xrpc.com.etzhayyim.apps.jpAshiba.changeTier": task_jp_ashiba_change_tier,
        "xrpc.com.etzhayyim.apps.jpAshiba.checkAvailability": task_jp_ashiba_check_availability,
        "xrpc.com.etzhayyim.apps.jpAshiba.confirmRental": task_jp_ashiba_confirm_rental,
        "xrpc.com.etzhayyim.apps.jpAshiba.createQuote": task_jp_ashiba_create_quote,
        "xrpc.com.etzhayyim.apps.jpAshiba.extendRental": task_jp_ashiba_extend_rental,
        "xrpc.com.etzhayyim.apps.jpAshiba.getItem": task_jp_ashiba_get_item,
        "xrpc.com.etzhayyim.apps.jpAshiba.getUsageSummary": task_jp_ashiba_get_usage_summary,
        "xrpc.com.etzhayyim.apps.jpAshiba.listCatalog": task_jp_ashiba_list_catalog,
        "xrpc.com.etzhayyim.apps.jpAshiba.recordInspection": task_jp_ashiba_record_inspection,
        "xrpc.com.etzhayyim.apps.jpAshiba.reportDefect": task_jp_ashiba_report_defect,
        "xrpc.com.etzhayyim.apps.jpAshiba.returnRental": task_jp_ashiba_return_rental,
        "xrpc.com.etzhayyim.apps.jpAshiba.scheduleDelivery": task_jp_ashiba_schedule_delivery,
        "xrpc.com.etzhayyim.apps.jpAshiba.subscribe": task_jp_ashiba_subscribe,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)

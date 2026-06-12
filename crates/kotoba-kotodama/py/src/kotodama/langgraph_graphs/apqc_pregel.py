"""APQC LangServer Pregel graphs — 13 L1 BSP super-steps + L2 Send fan-out.

Topology (flat graph, two BSP layers):
  START
    ↓ conditional_edges → dispatch_l1s → [Send×13] → l1_coord (BSP super-step)
    ↓ conditional_edges → l1_coord    → [Send×N]  → l2_task / l2_materialize (BSP super-step)
    ↓ edge → l2_* → END
  All node outputs merge into ApqcOrchestratorState via Annotated[list, operator.add] reducers.

Archive reference:
  _archive/2026-05-14-kyber-projector-wasm-kyb3proj/  (TS WASM, kept for reference)

DB registration: alembic/versions/20260514_0001_apqc_pregel_langgraph_assistant_seed.py
"""

from __future__ import annotations

import json
import operator
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client
try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

    _LANGGRAPH_OK = True
except ImportError:  # pragma: no cover
    END = "END"  # type: ignore[assignment]
    START = "START"  # type: ignore[assignment]
    StateGraph = object  # type: ignore[assignment]
    Send = None  # type: ignore[assignment]
    _LANGGRAPH_OK = False


# ─────────────────────────────────── catalog ────────────────────────────────

PROJECTOR_DID = "did:web:kyber-projector.etzhayyim.com"
ACTOR_ID = "sys.worker.apqc.pregel"

APQC_L1: list[dict[str, Any]] = [
    {"code": "1.0",  "slug": "1-vision-strategy",      "name": "Vision & Strategy",       "subProcesses": 7},
    {"code": "2.0",  "slug": "2-product-service",       "name": "Product & Service",       "subProcesses": 9},
    {"code": "3.0",  "slug": "3-market-sell",           "name": "Market & Sell",           "subProcesses": 12},
    {"code": "4.0",  "slug": "4-supply-chain",          "name": "Supply Chain",            "subProcesses": 9},
    {"code": "5.0",  "slug": "5-production-ops",        "name": "Production / Operations", "subProcesses": 3},
    {"code": "6.0",  "slug": "6-customer-service",      "name": "Customer Service",        "subProcesses": 6},
    {"code": "7.0",  "slug": "7-human-capital",         "name": "Human Capital",           "subProcesses": 14},
    {"code": "8.0",  "slug": "8-info-technology",       "name": "Information Technology",  "subProcesses": 16},
    {"code": "9.0",  "slug": "9-financial-resources",   "name": "Financial Resources",     "subProcesses": 20},
    {"code": "10.0", "slug": "10-asset-management",     "name": "Asset Management",        "subProcesses": 13},
    {"code": "11.0", "slug": "11-risk-compliance",      "name": "Risk & Compliance",       "subProcesses": 21},
    {"code": "12.0", "slug": "12-external-relations",   "name": "External Relations",      "subProcesses": 49},
    {"code": "13.0", "slug": "13-business-capability",  "name": "Business Capability",     "subProcesses": 4},
]

L1_BY_CODE: dict[str, dict[str, Any]] = {l["code"]: l for l in APQC_L1}

# 28 BPMN task bindings — ported from _archive/2026-05-14-kyber-projector-wasm-kyb3proj/src/app.ts
BPMN_CATALOG: list[dict[str, Any]] = [
    # 1.0 Vision & Strategy
    {"taskId": "bpmn-1-strategy-define",     "apqcCode": "1.0",  "taskType": "userTask",         "name": "Define corporate strategy",           "ocelEventType": "strategy.defined"},
    {"taskId": "bpmn-1-okr-publish",         "apqcCode": "1.0",  "taskType": "sendTask",         "name": "Publish OKRs",                        "ocelEventType": "okr.published"},
    # 2.0 Product & Service
    {"taskId": "bpmn-2-product-design",      "apqcCode": "2.0",  "taskType": "userTask",         "name": "Design product / service",            "ocelEventType": "product.designed"},
    {"taskId": "bpmn-2-sku-activate",        "apqcCode": "2.0",  "taskType": "serviceTask",      "name": "Activate SKU in catalog",             "ocelEventType": "sku.activated"},
    # 3.0 Market & Sell
    {"taskId": "bpmn-3-sales-order-intake",  "apqcCode": "3.0",  "taskType": "receiveTask",      "name": "Intake sales order",                  "ocelEventType": "sales.ordered",       "kyberCollection": "com.etzhayyim.apps.kyber.salesOrder"},
    {"taskId": "bpmn-3-order-confirm",       "apqcCode": "3.0",  "taskType": "serviceTask",      "name": "Confirm sales order",                 "ocelEventType": "sales.confirmed"},
    # 4.0 Supply Chain
    {"taskId": "bpmn-4-po-create",           "apqcCode": "4.0",  "taskType": "receiveTask",      "name": "Create purchase order",               "ocelEventType": "po.created",          "kyberCollection": "com.etzhayyim.apps.kyber.purchaseOrder"},
    {"taskId": "bpmn-4-po-approve",          "apqcCode": "4.0",  "taskType": "userTask",         "name": "Approve purchase order",              "ocelEventType": "po.approved"},
    {"taskId": "bpmn-4-grn-post",            "apqcCode": "4.0",  "taskType": "serviceTask",      "name": "Goods receipt note",                  "ocelEventType": "grn.posted"},
    # 5.0 Production / Operations
    {"taskId": "bpmn-5-workorder-release",   "apqcCode": "5.0",  "taskType": "serviceTask",      "name": "Release production work order",       "ocelEventType": "workorder.released"},
    # 6.0 Customer Service
    {"taskId": "bpmn-6-case-open",           "apqcCode": "6.0",  "taskType": "receiveTask",      "name": "Open support case",                   "ocelEventType": "case.opened"},
    {"taskId": "bpmn-6-case-resolve",        "apqcCode": "6.0",  "taskType": "userTask",         "name": "Resolve support case",                "ocelEventType": "case.resolved"},
    # 7.0 Human Capital
    {"taskId": "bpmn-7-employee-onboard",    "apqcCode": "7.0",  "taskType": "receiveTask",      "name": "Onboard employee",                    "ocelEventType": "employee.onboarded",  "kyberCollection": "com.etzhayyim.apps.kyber.employee"},
    {"taskId": "bpmn-7-payroll-run",         "apqcCode": "7.0",  "taskType": "serviceTask",      "name": "Run payroll",                         "ocelEventType": "payroll.ran"},
    # 8.0 Information Technology
    {"taskId": "bpmn-8-incident-triage",     "apqcCode": "8.0",  "taskType": "userTask",         "name": "Triage IT incident",                  "ocelEventType": "incident.triaged"},
    {"taskId": "bpmn-8-change-deploy",       "apqcCode": "8.0",  "taskType": "serviceTask",      "name": "Deploy change release",               "ocelEventType": "change.deployed"},
    # 9.0 Financial Resources
    {"taskId": "bpmn-9-journal-post",        "apqcCode": "9.0",  "taskType": "receiveTask",      "name": "Post GL journal",                     "ocelEventType": "journal.posted",      "kyberCollection": "com.etzhayyim.apps.kyber.journalEntry"},
    {"taskId": "bpmn-9-coa-seed",            "apqcCode": "9.0",  "taskType": "serviceTask",      "name": "Seed chart of accounts",              "ocelEventType": "coa.seeded",          "kyberCollection": "com.etzhayyim.apps.kyber.account"},
    {"taskId": "bpmn-9-invoice-issue",       "apqcCode": "9.0",  "taskType": "receiveTask",      "name": "Issue invoice",                       "ocelEventType": "invoice.issued",      "kyberCollection": "com.etzhayyim.apps.kyber.invoice"},
    {"taskId": "bpmn-9-trial-balance",       "apqcCode": "9.0",  "taskType": "businessRuleTask", "name": "Compute trial balance",               "ocelEventType": "tb.computed"},
    # 10.0 Asset Management
    {"taskId": "bpmn-10-inventory-register", "apqcCode": "10.0", "taskType": "receiveTask",      "name": "Register inventory item",             "ocelEventType": "inventory.registered", "kyberCollection": "com.etzhayyim.apps.kyber.inventoryItem"},
    {"taskId": "bpmn-10-depreciation-run",   "apqcCode": "10.0", "taskType": "scriptTask",       "name": "Run monthly depreciation",            "ocelEventType": "depreciation.ran"},
    # 11.0 Risk & Compliance
    {"taskId": "bpmn-11-risk-assess",        "apqcCode": "11.0", "taskType": "businessRuleTask", "name": "Assess enterprise risk",              "ocelEventType": "risk.assessed"},
    {"taskId": "bpmn-11-audit-log",          "apqcCode": "11.0", "taskType": "serviceTask",      "name": "Record compliance audit event",       "ocelEventType": "audit.logged"},
    # 12.0 External Relations
    {"taskId": "bpmn-12-regulator-file",     "apqcCode": "12.0", "taskType": "sendTask",         "name": "File regulator report",               "ocelEventType": "regulator.filed"},
    {"taskId": "bpmn-12-investor-notify",    "apqcCode": "12.0", "taskType": "sendTask",         "name": "Notify investors",                    "ocelEventType": "investor.notified"},
    # 13.0 Business Capability
    {"taskId": "bpmn-13-capability-assess",  "apqcCode": "13.0", "taskType": "businessRuleTask", "name": "Assess business capability maturity", "ocelEventType": "capability.assessed"},
    {"taskId": "bpmn-13-process-mine",       "apqcCode": "13.0", "taskType": "scriptTask",       "name": "Mine OCEL log for process insights",  "ocelEventType": "process.mined"},
]

_CATALOG_BY_CODE: dict[str, list[dict[str, Any]]] = {}
for _b in BPMN_CATALOG:
    _CATALOG_BY_CODE.setdefault(_b["apqcCode"], []).append(_b)

_CATALOG_BY_ID: dict[str, dict[str, Any]] = {b["taskId"]: b for b in BPMN_CATALOG}


# ─────────────────────────────────── helpers ────────────────────────────────

def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gen_id(prefix: str = "ev") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _apqc_did(code: str) -> str:
    base = code if code in L1_BY_CODE else f"{code.split('.')[0]}.0"
    l1 = L1_BY_CODE.get(base)
    return f"{PROJECTOR_DID}:apqc:{l1['slug']}" if l1 else PROJECTOR_DID


def _emit_ocel(
    apqc_code: str,
    task_id: str,
    event_type: str,
    case_id: str,
    objects: list[dict[str, Any]],
    attributes: dict[str, Any],
    actor_did: str,
    dry_run: bool,
) -> str:
    l1 = L1_BY_CODE.get(apqc_code, {})
    event_id = _gen_id("ocel")
    vertex_id = f"at://{actor_did}/com.etzhayyim.apps.apqc.apqcEvent/{event_id}"
    ts = _now_iso()
    if not dry_run:
        get_kotoba_client().insert_row("vertex_apqc_event", {
            "vertex_id": vertex_id,
            "rkey": event_id,
            "repo": actor_did,
            "ocel_event_id": event_id,
            "apqc_code": apqc_code,
            "apqc_l1_name": l1.get('name', ''),
            "task_id": task_id or None,
            "event_type": event_type,
            "case_id": case_id or None,
            "objects_json": json.dumps(objects, ensure_ascii=False),
            "attributes_json": json.dumps(attributes, ensure_ascii=False),
            "timestamp": ts,
            "created_at": ts,
            "sensitivity_ord": 1,
            "owner_did": actor_did,
            "org_id": actor_did,
            "user_id": actor_did,
            "actor_id": ACTOR_ID,
            "actor_did": actor_did,
            "org_did": 'anon',
        })
    return event_id


# ─────────────────────────────────── state ──────────────────────────────────
# Single flat state type shared across all nodes.
# Send passes a partial dict; Annotated reducers accumulate results.

# Maps com.etzhayyim.kyber.projector.* NSID suffixes → internal mode
_NSID_MODE_MAP: dict[str, str] = {
    "registerApqcActors": "catalog",
    "listApqcActors":     "catalog",
    "listBpmnTasks":      "catalog",
    "listProcessGroups":  "catalog",
    "getProcessGroup":    "catalog",
    "listProcesses":      "catalog",
    "getProcess":         "catalog",
    "listActivities":     "catalog",
    "getActivity":        "catalog",
    "runBpmnTask":        "run_task",
    "getApqcCoverage":    "coverage",
    "emitApqcEvent":      "emit",
}


class ApqcOrchestratorState(TypedDict):
    # ── orchestrator inputs (set at graph invocation) ─────────────────────
    mode: str           # "materialize" | "run_task" | "coverage" | "catalog" | "emit"
    apqc_codes: list[str]   # L1 codes to process; [] = all 13
    task_id: str        # for run_task/catalog: target BPMN task id
    case_id: str
    variables: dict[str, Any]
    caller_did: str
    dry_run: bool
    # ── dispatcher-injected context ────────────────────────────────────────
    _nsid: str          # injected by dispatcher as process_vars["_nsid"]
    # ── per-invocation context (injected via Send per L1/L2 call) ─────────
    current_l1_code: str
    current_task_id: str
    current_task_type: str
    current_event_type: str
    current_actor_did: str
    current_case_id: str
    # ── fan-in accumulators ───────────────────────────────────────────────
    l1_results: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
    completed: bool


# ─────────────────────────────────── L1 BSP nodes ───────────────────────────

def _infer_mode(state: ApqcOrchestratorState) -> str:
    """Infer execution mode from explicit state field or injected _nsid suffix."""
    mode = state.get("mode", "")
    if mode:
        return mode
    nsid_val = state.get("_nsid", "")
    suffix = nsid_val.split(".")[-1] if nsid_val else ""
    return _NSID_MODE_MAP.get(suffix, "materialize")


def _normalize_codes(state: ApqcOrchestratorState) -> list[str]:
    """Return L1 codes from state, handling both snake_case and camelCase XRPC fields."""
    raw = state.get("apqc_codes") or state.get("apqcCodes", "")  # type: ignore[call-overload]
    if isinstance(raw, str):
        codes = [c.strip() for c in raw.split(",") if c.strip()]
    else:
        codes = list(raw or [])
    return codes or [l["code"] for l in APQC_L1]


def _dispatch_l1s(state: ApqcOrchestratorState) -> list[Any]:
    """Orchestrator → L1 fan-out via Send (BSP super-step 1).

    Handles NSID-driven mode inference for requests arriving from dispatcher
    with process_vars (camelCase XRPC fields + _nsid injection).
    """
    mode = _infer_mode(state)

    # Catalog / emit modes bypass L1 fan-out entirely.
    if mode in ("catalog", "emit"):
        return [Send("catalog_query", {**state, "mode": mode, "l1_results": [], "errors": []})]

    # Normalize camelCase XRPC body fields → snake_case state fields.
    task_id = state.get("task_id") or state.get("taskId", "")  # type: ignore[call-overload]
    case_id = state.get("case_id") or state.get("caseId", "")  # type: ignore[call-overload]
    codes = _normalize_codes(state)
    base: dict[str, Any] = {**state, "mode": mode, "task_id": task_id, "case_id": case_id, "apqc_codes": codes}

    sends = []
    for code in codes:
        if code not in L1_BY_CODE:
            continue
        sends.append(
            Send(
                "l1_coord",
                {
                    **base,
                    "current_l1_code": code,
                    "current_actor_did": _apqc_did(code),
                    "l1_results": [],
                    "errors": [],
                },
            )
        )
    return sends


def _l1_coord(state: ApqcOrchestratorState) -> list[Any]:
    """L1 coordinator (BSP super-step 2): fan-out to L2 task/materialize nodes via Send."""
    apqc_code = state.get("current_l1_code", "")
    mode = _infer_mode(state)
    actor_did = state.get("current_actor_did") or _apqc_did(apqc_code)

    if mode == "run_task":
        target = state.get("task_id", "")
        binding = _CATALOG_BY_ID.get(target)
        if not binding or binding["apqcCode"] != apqc_code:
            return []
        return [
            Send(
                "l2_task",
                {
                    **state,
                    "current_task_id": target,
                    "current_task_type": binding["taskType"],
                    "current_event_type": binding["ocelEventType"],
                    "current_actor_did": actor_did,
                    "current_case_id": state.get("case_id", "") or _gen_id("case"),
                    "l1_results": [],
                    "errors": [],
                },
            )
        ]

    if mode == "materialize":
        return [
            Send(
                "l2_materialize",
                {
                    **state,
                    "current_l1_code": apqc_code,
                    "current_actor_did": actor_did,
                    "l1_results": [],
                    "errors": [],
                },
            )
        ]

    # coverage: fan-out to all BPMN tasks bound to this L1
    bindings = _CATALOG_BY_CODE.get(apqc_code, [])
    return [
        Send(
            "l2_task",
            {
                **state,
                "current_task_id": b["taskId"],
                "current_task_type": b["taskType"],
                "current_event_type": b["ocelEventType"],
                "current_actor_did": actor_did,
                "current_case_id": state.get("case_id", "") or _gen_id("case"),
                "dry_run": True,  # coverage is always dry-run
                "l1_results": [],
                "errors": [],
            },
        )
        for b in bindings
    ]


# ─────────────────────────────────── L2 leaf nodes ──────────────────────────

def _l2_task(state: ApqcOrchestratorState) -> dict[str, Any]:
    """Execute one BPMN task: emit OCEL event (skipped if dry_run)."""
    task_id = state.get("current_task_id", "")
    apqc_code = state.get("current_l1_code", "")
    actor_did = state.get("current_actor_did") or _apqc_did(apqc_code)
    binding = _CATALOG_BY_ID.get(task_id, {})

    try:
        event_id = _emit_ocel(
            apqc_code=apqc_code,
            task_id=task_id,
            event_type=state.get("current_event_type", ""),
            case_id=state.get("current_case_id", ""),
            objects=[{"id": state.get("current_case_id", _gen_id("case")), "type": "processInstance"}],
            attributes={
                "taskType": state.get("current_task_type", ""),
                "name": binding.get("name", ""),
                "variables": state.get("variables", {}),
            },
            actor_did=actor_did,
            dry_run=state.get("dry_run", False),
        )
        # receiveTask / userTask remain "running" until external completion
        auto_complete = state.get("current_task_type", "") not in ("userTask", "receiveTask")
        return {
            "l1_results": [{
                "task_id": task_id,
                "apqc_code": apqc_code,
                "ocel_event_id": event_id,
                "actor_did": actor_did,
                "status": "completed" if auto_complete else "running",
            }],
            "errors": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "l1_results": [{"task_id": task_id, "apqc_code": apqc_code, "status": "error"}],
            "errors": [str(exc)],
        }


def _l2_materialize(state: ApqcOrchestratorState) -> dict[str, Any]:
    """Materialize L2 subprocess list for one L1 code (no DB write)."""
    apqc_code = state.get("current_l1_code", "")
    l1 = L1_BY_CODE.get(apqc_code, {})
    actor_did = state.get("current_actor_did") or _apqc_did(apqc_code)
    sub_count = int(l1.get("subProcesses", 0))
    sub_codes = [f"{apqc_code}.{i}" for i in range(1, sub_count + 1)]
    return {
        "l1_results": [{
            "apqc_code": apqc_code,
            "name": l1.get("name", ""),
            "actor_did": actor_did,
            "subprocesses": sub_codes,
            "status": "materialized",
        }],
        "errors": [],
    }


def _catalog_query(state: ApqcOrchestratorState) -> dict[str, Any]:
    """Serve com.etzhayyim.kyber.projector.list*/get*/register* + emitApqcEvent without L1 fan-out."""
    nsid_val = state.get("_nsid", "")
    suffix = nsid_val.split(".")[-1] if nsid_val else ""
    mode = state.get("mode", "catalog")

    # Resolve apqcCode from either snake_case or camelCase field.
    apqc_code: str = (
        state.get("apqc_code", "")  # type: ignore[call-overload]
        or state.get("apqcCode", "")  # type: ignore[call-overload]
        or (state.get("apqc_codes") or [""])[0]
    )
    task_id: str = state.get("task_id", "") or state.get("taskId", "")  # type: ignore[call-overload]

    if suffix in ("registerApqcActors", "listApqcActors"):
        actors = [
            {"apqcCode": l["code"], "slug": l["slug"], "name": l["name"],
             "subProcesses": l["subProcesses"], "did": _apqc_did(l["code"])}
            for l in APQC_L1
        ]
        return {"l1_results": [{"ok": True, "query": suffix, "actors": actors, "count": len(actors)}], "errors": []}

    if suffix == "listBpmnTasks":
        return {"l1_results": [{"ok": True, "query": suffix, "tasks": BPMN_CATALOG, "count": len(BPMN_CATALOG)}], "errors": []}

    if suffix == "listProcessGroups":
        groups = [{"code": l["code"], "slug": l["slug"], "name": l["name"], "subProcesses": l["subProcesses"]} for l in APQC_L1]
        return {"l1_results": [{"ok": True, "query": suffix, "groups": groups, "count": len(groups)}], "errors": []}

    if suffix == "getProcessGroup":
        l1 = L1_BY_CODE.get(apqc_code)
        if not l1:
            return {"l1_results": [], "errors": [f"unknown apqcCode: {apqc_code}"]}
        return {"l1_results": [{"ok": True, "query": suffix, "group": l1, "did": _apqc_did(apqc_code)}], "errors": []}

    if suffix == "listProcesses":
        l1 = L1_BY_CODE.get(apqc_code, {})
        sub_count = int(l1.get("subProcesses", 0))
        procs = [{"apqcCode": f"{apqc_code}.{i}", "l1Code": apqc_code, "did": _apqc_did(apqc_code)} for i in range(1, sub_count + 1)]
        return {"l1_results": [{"ok": True, "query": suffix, "processes": procs, "count": len(procs)}], "errors": []}

    if suffix == "getProcess":
        l1_code = apqc_code.split(".")[0] + ".0" if "." in apqc_code else apqc_code
        l1 = L1_BY_CODE.get(l1_code, {})
        return {"l1_results": [{"ok": True, "query": suffix, "process": {"apqcCode": apqc_code, "l1": l1, "did": _apqc_did(apqc_code)}}], "errors": []}

    if suffix == "listActivities":
        tasks = [b for b in BPMN_CATALOG if not apqc_code or b["apqcCode"] == apqc_code]
        return {"l1_results": [{"ok": True, "query": suffix, "activities": tasks, "count": len(tasks)}], "errors": []}

    if suffix == "getActivity":
        binding = _CATALOG_BY_ID.get(task_id, {})
        if not binding:
            return {"l1_results": [], "errors": [f"unknown taskId: {task_id}"]}
        return {"l1_results": [{"ok": True, "query": suffix, "activity": binding}], "errors": []}

    if suffix == "emitApqcEvent" or mode == "emit":
        # Delegate to OCEL emit — resolve fields from camelCase XRPC body.
        apqc_code_emit: str = (
            state.get("apqcCode", "")  # type: ignore[call-overload]
            or state.get("apqc_code", "")  # type: ignore[call-overload]
        )
        event_type: str = state.get("eventType", "") or state.get("event_type", "")  # type: ignore[call-overload]
        actor_did: str = state.get("actorDid", "") or _apqc_did(apqc_code_emit)  # type: ignore[call-overload]
        dry_run: bool = bool(state.get("dry_run") or state.get("dryRun"))  # type: ignore[call-overload]
        objects: list[Any] = state.get("objects", [])  # type: ignore[call-overload]
        attributes: dict[str, Any] = state.get("attributes", {})  # type: ignore[call-overload]
        try:
            event_id = _emit_ocel(
                apqc_code=apqc_code_emit,
                task_id=task_id,
                event_type=event_type,
                case_id=state.get("case_id", "") or state.get("caseId", ""),  # type: ignore[call-overload]
                objects=objects if isinstance(objects, list) else [],
                attributes=attributes if isinstance(attributes, dict) else {},
                actor_did=actor_did,
                dry_run=dry_run,
            )
            return {"l1_results": [{"ok": True, "ocelEventId": event_id, "apqcCode": apqc_code_emit, "eventType": event_type}], "errors": []}
        except Exception as exc:  # noqa: BLE001
            return {"l1_results": [], "errors": [str(exc)]}

    return {"l1_results": [{"ok": False, "query": suffix, "error": "unrecognized catalog query"}], "errors": []}


def _finalize(state: ApqcOrchestratorState) -> dict[str, Any]:
    return {"completed": True}


# ─────────────────────────────────── graph factory ──────────────────────────

def build_graph() -> Any:
    """Build and compile the APQC Pregel orchestrator graph.

    BSP super-step 1 (L1 fan-out):
      START → conditional_edges(_dispatch_l1s) → [Send×13] → l1_coord

    BSP super-step 2 (L2 fan-out within each L1):
      l1_coord → conditional_edges(_l1_coord) → [Send×N] → l2_task | l2_materialize

    Fan-in:
      l2_* → l1_results (Annotated[list, operator.add]) → finalize → END
    """
    if not _LANGGRAPH_OK:
        return None

    g = StateGraph(ApqcOrchestratorState)

    # stub entry so conditional_edges has a named source node
    g.add_node("dispatch_l1s", lambda s: {})
    g.add_node("l1_coord", lambda s: {})
    g.add_node("l2_task", _l2_task)
    g.add_node("l2_materialize", _l2_materialize)
    g.add_node("catalog_query", _catalog_query)
    g.add_node("finalize", _finalize)

    # edges
    g.set_entry_point("dispatch_l1s")
    g.add_conditional_edges("dispatch_l1s", _dispatch_l1s, ["l1_coord", "catalog_query"])
    g.add_conditional_edges("l1_coord", _l1_coord, ["l2_task", "l2_materialize"])
    g.add_edge("l2_task", "finalize")
    g.add_edge("l2_materialize", "finalize")
    g.add_edge("catalog_query", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


# ─────────────────────────────────── task API ───────────────────────────────

def _base_state(
    mode: str,
    codes: list[str],
    task_id: str,
    case_id: str,
    variables: dict[str, Any],
    caller_did: str,
    dry_run: bool,
) -> ApqcOrchestratorState:
    return ApqcOrchestratorState(
        mode=mode,
        apqc_codes=codes,
        task_id=task_id,
        case_id=case_id,
        variables=variables,
        caller_did=caller_did or PROJECTOR_DID,
        dry_run=dry_run,
        _nsid="",
        current_l1_code="",
        current_task_id="",
        current_task_type="",
        current_event_type="",
        current_actor_did="",
        current_case_id="",
        l1_results=[],
        errors=[],
        completed=False,
    )


async def task_apqc_pregel_materialize(
    apqcCodes: str = "",
    dryRun: bool = False,
    callerDid: str = "",
) -> dict[str, Any]:
    """Materialize all (or specific) L1 subprocess trees via Pregel fan-out."""
    codes = [c.strip() for c in apqcCodes.split(",") if c.strip()] if apqcCodes else []
    invalid = [c for c in codes if c not in L1_BY_CODE]
    if invalid:
        return {"ok": False, "error": f"unknown apqcCode(s): {invalid}"}

    graph = build_graph()
    if graph is None:
        return {"ok": False, "error": "LangGraph not available"}

    result: ApqcOrchestratorState = await graph.ainvoke(
        _base_state("materialize", codes, "", "", {}, callerDid, dryRun)
    )
    return {
        "ok": True,
        "mode": "materialize",
        "l1Count": len(result.get("l1_results", [])),
        "l1Results": result.get("l1_results", []),
        "errors": result.get("errors", []),
        "dryRun": dryRun,
    }


async def task_apqc_pregel_run_bpmn(
    taskId: str = "",
    caseId: str = "",
    variables: Any = None,
    dryRun: bool = False,
    callerDid: str = "",
) -> dict[str, Any]:
    """Execute one BPMN task via Pregel (single L1 → single L2 leaf)."""
    binding = _CATALOG_BY_ID.get(taskId)
    if not binding:
        return {"ok": False, "error": f"unknown taskId: {taskId}"}

    graph = build_graph()
    if graph is None:
        return {"ok": False, "error": "LangGraph not available"}

    apqc_code = binding["apqcCode"]
    result: ApqcOrchestratorState = await graph.ainvoke(
        _base_state(
            "run_task",
            [apqc_code],
            taskId,
            caseId or _gen_id("case"),
            variables or {},
            callerDid,
            dryRun,
        )
    )
    results = result.get("l1_results", [])
    leaf = results[0] if results else {}
    return {
        "ok": not result.get("errors"),
        "taskId": taskId,
        "apqcCode": apqc_code,
        "ocelEventId": leaf.get("ocel_event_id", ""),
        "status": leaf.get("status", "unknown"),
        "actorDid": leaf.get("actor_did", _apqc_did(apqc_code)),
        "errors": result.get("errors", []),
        "dryRun": dryRun,
    }


async def task_apqc_pregel_coverage(
    apqcCodes: str = "",
    callerDid: str = "",
) -> dict[str, Any]:
    """Dry-run coverage sweep: confirm all 28 BPMN tasks are reachable."""
    codes = [c.strip() for c in apqcCodes.split(",") if c.strip()] if apqcCodes else []

    graph = build_graph()
    if graph is None:
        return {"ok": False, "error": "LangGraph not available"}

    result: ApqcOrchestratorState = await graph.ainvoke(
        _base_state("coverage", codes, "", "", {}, callerDid, True)
    )
    l1_results = result.get("l1_results", [])
    return {
        "ok": True,
        "mode": "coverage",
        "registeredL1": len(APQC_L1),
        "scannedL1": len({r.get("apqc_code") for r in l1_results}),
        "totalBpmnTasks": len(BPMN_CATALOG),
        "coveredTasks": len(l1_results),
        "byTask": l1_results,
        "errors": result.get("errors", []),
    }

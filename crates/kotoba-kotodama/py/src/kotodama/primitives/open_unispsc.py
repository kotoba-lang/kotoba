"""open-unispsc primitives.

UNSPSC is handled as four business boundaries, not just one code string:

* segment   (2 digits): portfolio / domain ownership
* family    (4 digits): category-management policy
* class     (6 digits): control and compliance policy
* commodity (8 digits): executable procurement policy

The MCP surface exposes one tool per boundary.  Each tool validates its own
code shape, derives parent hierarchy, and returns a deterministic business
logic contract that LangGraph nodes and callers can consume.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypedDict


OPEN_UNISPSC_DID = "did:web:etzhayyim.com:actor:open-unispsc"
OPEN_UNISPSC_DID_LEGACY = "did:web:unispsc.etzhayyim.com"
ACTOR_ID = "sys.worker.open-unispsc"
Level = Literal["segment", "family", "class", "commodity"]

_LEVEL_DIGITS: dict[Level, int] = {
    "segment": 2,
    "family": 4,
    "class": 6,
    "commodity": 8,
}
_CODE_RE = re.compile(r"^\d{2}(\d{2}){0,3}$")

_GRAPH_TABLES: dict[str, dict[str, set[str] | str]] = {
    "vertex_open_unispsc_supplier": {
        "key": "vertex_id",
        "columns": {
            "vertex_id", "_seq", "created_date", "sensitivity_ord", "owner_did",
            "supplier_did", "commodity_code", "legal_name", "country",
            "kyc_cleared", "quality_score", "risk_tier", "require_manual_kyc",
            "status", "registered_at", "created_at", "org_id", "user_id", "actor_id",
        },
    },
    "vertex_open_unispsc_procurement": {
        "key": "vertex_id",
        "columns": {
            "vertex_id", "_seq", "created_date", "sensitivity_ord", "owner_did",
            "buyer_org_id", "commodity_code", "quantity", "unit_price", "currency",
            "total_amount", "dangerous_goods", "sanctions_check", "approval_tier",
            "require_cab", "status", "submitted_at", "approved_at", "settled_at",
            "created_at", "org_id", "user_id", "actor_id",
        },
    },
    "edge_open_unispsc_procurement_commodity": {
        "key": "edge_id",
        "columns": {
            "edge_id", "_seq", "created_date", "sensitivity_ord", "owner_did",
            "src_vid", "dst_vid", "role", "created_at", "org_id", "user_id", "actor_id",
        },
    },
    "vertex_open_defence_event": {
        "key": "vertex_id",
        "columns": {
            "vertex_id", "owner_did", "bpmn_process_id", "nsid", "project",
            "subject_vid", "action_class", "severity", "detected_at", "created_at",
            "sensitivity_ord", "org_id", "user_id", "actor_id", "commodity_code",
            "evidence_uri", "confidence", "actor_did", "org_did",
        },
    },
}

_EXPECTED_TOOL_SPECS: list[dict[str, Any]] = [
    {"method": "segment", "nsid": "com.etzhayyim.apps.openUnispsc.segment", "lexicon": "segment.json", "bpmn": [], "graphTargets": []},
    {"method": "family", "nsid": "com.etzhayyim.apps.openUnispsc.family", "lexicon": "family.json", "bpmn": [], "graphTargets": []},
    {"method": "class", "nsid": "com.etzhayyim.apps.openUnispsc.class", "lexicon": "class.json", "bpmn": [], "graphTargets": []},
    {"method": "commodity", "nsid": "com.etzhayyim.apps.openUnispsc.commodity", "lexicon": "commodity.json", "bpmn": [], "graphTargets": []},
    {"method": "designItem", "nsid": "com.etzhayyim.apps.openUnispsc.designItem", "lexicon": "designItem.json", "bpmn": ["procurement.bpmn", "supplier.bpmn", "flagArmsCommodity.bpmn", "flagDualUseCommodity.bpmn"], "graphTargets": []},
    {"method": "itemGetSpec", "nsid": "com.etzhayyim.apps.openUnispsc.itemGetSpec", "lexicon": "itemGetSpec.json", "bpmn": ["procurement.bpmn", "supplier.bpmn"], "graphTargets": []},
    {"method": "itemScreenSupplier", "nsid": "com.etzhayyim.apps.openUnispsc.itemScreenSupplier", "lexicon": "itemScreenSupplier.json", "bpmn": ["supplier.bpmn"], "graphTargets": []},
    {"method": "itemPlanProcurement", "nsid": "com.etzhayyim.apps.openUnispsc.itemPlanProcurement", "lexicon": "itemPlanProcurement.json", "bpmn": ["procurement.bpmn"], "graphTargets": []},
    {"method": "itemFlagCompliance", "nsid": "com.etzhayyim.apps.openUnispsc.itemFlagCompliance", "lexicon": "itemFlagCompliance.json", "bpmn": ["flagArmsCommodity.bpmn", "flagDualUseCommodity.bpmn"], "graphTargets": []},
    {"method": "syncCatalogItem", "nsid": "com.etzhayyim.apps.openUnispsc.syncCatalogItem", "lexicon": "syncCatalogItem.json", "bpmn": [], "graphTargets": []},
    {"method": "planCatalogPurchase", "nsid": "com.etzhayyim.apps.openUnispsc.planCatalogPurchase", "lexicon": "planCatalogPurchase.json", "bpmn": ["procurement.bpmn"], "graphTargets": []},
    {"method": "syncAllCommodityDids", "nsid": "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids", "lexicon": "syncAllCommodityDids.json", "bpmn": [], "graphTargets": []},
    {"method": "importSegmentCatalog", "nsid": "com.etzhayyim.apps.openUnispsc.importSegmentCatalog", "lexicon": "importSegmentCatalog.json", "bpmn": [], "graphTargets": []},
    {"method": "supplier", "nsid": "com.etzhayyim.apps.openUnispsc.supplier", "lexicon": "supplier.json", "bpmn": ["supplier.bpmn"], "graphTargets": ["vertex_open_unispsc_supplier"]},
    {"method": "procurement", "nsid": "com.etzhayyim.apps.openUnispsc.procurement", "lexicon": "procurement.json", "bpmn": ["procurement.bpmn"], "graphTargets": ["vertex_open_unispsc_procurement", "edge_open_unispsc_procurement_commodity"]},
    {"method": "flagArmsCommodity", "nsid": "com.etzhayyim.apps.openUnispsc.flagArmsCommodity", "lexicon": "flagArmsCommodity.json", "bpmn": ["flagArmsCommodity.bpmn"], "graphTargets": ["vertex_open_defence_event"]},
    {"method": "flagDualUseCommodity", "nsid": "com.etzhayyim.apps.openUnispsc.flagDualUseCommodity", "lexicon": "flagDualUseCommodity.json", "bpmn": ["flagDualUseCommodity.bpmn"], "graphTargets": ["vertex_open_defence_event"]},
    {"method": "applyGraphWritePlan", "nsid": "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan", "lexicon": "applyGraphWritePlan.json", "bpmn": [], "graphTargets": list(_GRAPH_TABLES.keys())},
    {"method": "runItemWorkflow", "nsid": "com.etzhayyim.apps.openUnispsc.runItemWorkflow", "lexicon": "runItemWorkflow.json", "bpmn": ["procurement.bpmn", "supplier.bpmn", "flagArmsCommodity.bpmn", "flagDualUseCommodity.bpmn"], "graphTargets": list(_GRAPH_TABLES.keys())},
    {"method": "coverageSnapshot", "nsid": "com.etzhayyim.apps.openUnispsc.coverageSnapshot", "lexicon": "coverageSnapshot.json", "bpmn": [], "graphTargets": []},
]


class UnispscRecord(TypedDict, total=False):
    ok: bool
    level: Level
    code: str
    name: str
    did: str
    parentLevel: str
    parentCode: str
    parentDid: str
    hierarchy: dict[str, str]
    businessLogic: dict[str, Any]
    mcpTool: str
    dryRun: bool
    createdAt: str
    error: str


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "60-apps").exists() and (parent / "20-actors").exists():
            return parent
    return here.parents[6]


def _segments_csv() -> Path:
    return _repo_root() / "60-apps/etzhayyim-project-open-unispsc/segments.csv"


def _lexicon_dir() -> Path:
    return _repo_root() / "00-contracts/lexicons/com/etzhayyim/apps/openUnispsc"


def _bpmn_contract_dir() -> Path:
    return _repo_root() / "00-contracts/bpmn/com/etzhayyim/open-unispsc"


def _mcp_seed_sql() -> Path:
    return _repo_root() / "30-graph/graph-schema/sql_migrations/20260514010000_seed_open_unispsc_hierarchy_mcp.up.sql"


def _mcp_seed_down_sql() -> Path:
    return _repo_root() / "30-graph/graph-schema/sql_migrations/20260514010000_seed_open_unispsc_hierarchy_mcp.down.sql"


def _mcp_alembic_wrapper() -> Path:
    return _repo_root() / "30-graph/graph-schema/alembic/current_versions/r_20260514010000_seed_open_unispsc_hierarchy_mcp.py"


def _snake_method(method: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", method).lower()


def _lexicon_json_valid(path: Path, nsid: str) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return data.get("id") == nsid and bool(data.get("defs"))


def _load_segments() -> dict[str, dict[str, str]]:
    try:
        with _segments_csv().open(encoding="utf-8", newline="") as fh:
            return {row["code"]: row for row in csv.DictReader(fh)}
    except OSError:
        return {}


def _norm_code(code: str, level: Level) -> str:
    norm = "".join(ch for ch in str(code or "") if ch.isdigit())
    expected = _LEVEL_DIGITS[level]
    if len(norm) != expected or not _CODE_RE.match(norm):
        raise ValueError(f"{level} code must be exactly {expected} digits")
    return norm


def _level_for_code(code: str) -> Level:
    length = len(code)
    for level, digits in _LEVEL_DIGITS.items():
        if digits == length:
            return level
    raise ValueError(f"unsupported UNSPSC code length: {length}")


def _did(level: Level, code: str) -> str:
    if level == "segment":
        return f"{OPEN_UNISPSC_DID}:seg{code}"
    if level == "family":
        return f"{OPEN_UNISPSC_DID}:seg{code[:2]}:family:f{code}"
    if level == "class":
        return f"{OPEN_UNISPSC_DID}:seg{code[:2]}:family:f{code[:4]}:class:c{code}"
    return f"{OPEN_UNISPSC_DID}:seg{code[:2]}:commodity:c{code}"


def _hierarchy(code: str) -> dict[str, str]:
    return {
        "segment": code[:2],
        "family": code[:4] if len(code) >= 4 else "",
        "class": code[:6] if len(code) >= 6 else "",
        "commodity": code[:8] if len(code) >= 8 else "",
    }


def _parent(level: Level, code: str) -> tuple[str, str]:
    if level == "segment":
        return "", ""
    if level == "family":
        return "segment", code[:2]
    if level == "class":
        return "family", code[:4]
    return "class", code[:6]


def _approval_tier(code: str, *, dangerous_goods: bool = False, sanctions_check: str = "") -> str:
    segment = code[:2]
    if dangerous_goods or segment in {"12", "46", "51"} or sanctions_check.lower() in {"hit", "review"}:
        return "cab-required"
    if segment in {"71", "72", "73", "80", "81", "85", "92"}:
        return "managed-service"
    return "standard"


def _category_strategy(code: str) -> str:
    segment = code[:2]
    if segment == "46":
        return "controlled-safety-and-defense"
    if segment == "51":
        return "regulated-pharmaceutical"
    if int(segment) >= 70:
        return "service-category-management"
    if segment in {"20", "21", "22", "23", "24", "26", "27", "30", "31", "32", "39", "40", "41", "44", "45"}:
        return "capital-and-operating-supplies"
    return "goods-category-management"


def _risk_tags(code: str, *, dangerous_goods: bool = False, sanctions_check: str = "") -> list[str]:
    tags: list[str] = []
    segment = code[:2]
    if segment == "46":
        tags.append("arms-or-security-review")
    if segment == "51":
        tags.append("regulated-health-product")
    if segment == "12" or dangerous_goods:
        tags.append("dangerous-goods")
    if sanctions_check:
        tags.append(f"sanctions:{sanctions_check}")
    if int(segment) >= 70:
        tags.append("service-delivery-risk")
    return tags


def _tool_name(level: Level) -> str:
    return f"com.etzhayyim.apps.openUnispsc.{level}"


def _stable_int(*parts: Any) -> int:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def _vertex_id(collection: str, *parts: Any) -> str:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
    return f"at://{OPEN_UNISPSC_DID}/{collection}/{digest}"


def _commodity_did(code: str) -> str:
    return f"{OPEN_UNISPSC_DID}:seg{code[:2]}:commodity:c{code}"


def _code_from_product_id(product_id: str) -> str:
    match = re.fullmatch(r"unispsc-(\d{8})", str(product_id or ""))
    if not match:
        raise ValueError("productId must match unispsc-{8-digit-code}")
    return match.group(1)


def _base_graph_row(timestamp: str) -> dict[str, Any]:
    created_at = timestamp or _now_iso()
    return {
        "_seq": 0,
        "created_date": created_at[:10],
        "sensitivity_ord": 0,
        "owner_did": OPEN_UNISPSC_DID,
        "created_at": created_at,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": ACTOR_ID,
    }


def _base_defence_event_row(timestamp: str, owner_did: str) -> dict[str, Any]:
    created_at = timestamp or _now_iso()
    return {
        "owner_did": owner_did,
        "detected_at": created_at,
        "created_at": created_at,
        "sensitivity_ord": 1,
        "org_id": owner_did,
        "user_id": owner_did,
        "actor_id": "sys.bpmn.open-defence",
        "actor_did": owner_did,
        "org_did": owner_did,
    }


def _graph_write_plan(*, operation: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": "deterministic-upsert",
        "operation": operation,
        "rows": rows,
    }


def _merge_graph_write_plans(operation: str, *plans: dict[str, Any] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        for row in plan.get("rows") or []:
            if not isinstance(row, dict):
                continue
            table = str(row.get("table") or "")
            key = str(row.get("key") or "")
            record = row.get("record") if isinstance(row.get("record"), dict) else {}
            row_id = str(record.get(key) or "")
            marker = (table, key, row_id)
            if marker in seen:
                continue
            seen.add(marker)
            rows.append(row)
    return _graph_write_plan(operation=operation, rows=rows)


def _validate_graph_write_plan(plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return [], ["graphWritePlan must be an object"]
    if plan.get("mode") != "deterministic-upsert":
        errors.append("graphWritePlan.mode must be deterministic-upsert")
    rows = plan.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("graphWritePlan.rows must be a non-empty array")
        return [], errors

    validated: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"rows[{index}] must be an object")
            continue
        table = str(row.get("table") or "")
        spec = _GRAPH_TABLES.get(table)
        if not spec:
            errors.append(f"rows[{index}].table is not an allowed openUnispsc graph table: {table}")
            continue
        key = str(row.get("key") or "")
        expected_key = str(spec["key"])
        if key != expected_key:
            errors.append(f"rows[{index}].key must be {expected_key}")
        record = row.get("record")
        if not isinstance(record, dict) or not record:
            errors.append(f"rows[{index}].record must be a non-empty object")
            continue
        if not record.get(expected_key):
            errors.append(f"rows[{index}].record.{expected_key} is required")
        allowed_columns = spec["columns"]
        assert isinstance(allowed_columns, set)
        bad_columns = sorted(str(col) for col in record if str(col) not in allowed_columns)
        if bad_columns:
            errors.append(f"rows[{index}].record has unsupported columns: {bad_columns}")
        if not bad_columns and key == expected_key and record.get(expected_key):
            validated.append({"table": table, "key": key, "record": dict(record)})
    return validated, errors


def _sql_for_graph_row(row: dict[str, Any]) -> tuple[str, list[Any]]:
    table = row["table"]
    key = row["key"]
    record = row["record"]
    columns = list(record.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(columns)
    updates = ", ".join(f"{col}=EXCLUDED.{col}" for col in columns if col != key)
    sql = (
        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) "
        f"ON CONFLICT ({key}) DO UPDATE SET {updates}"
    )
    return sql, [record[col] for col in columns]


def _statement_preview(sql: str, params: list[Any]) -> dict[str, Any]:
    return {"sql": sql, "parameters": params}


def _record(
    *,
    level: Level,
    code: str,
    name: str = "",
    dry_run: bool = False,
    quantity: float | None = None,
    unit_price: float | None = None,
    currency: str = "USD",
    dangerous_goods: bool = False,
    sanctions_check: str = "",
) -> UnispscRecord:
    parent_level, parent_code = _parent(level, code)
    segment_catalog = _load_segments()
    segment_name = segment_catalog.get(code[:2], {}).get("name", "")
    risk_tags = _risk_tags(code, dangerous_goods=dangerous_goods, sanctions_check=sanctions_check)
    total_amount = None
    if level == "commodity" and quantity is not None and unit_price is not None:
        total_amount = float(quantity) * float(unit_price)

    logic: dict[str, Any] = {
        "strategy": _category_strategy(code),
        "approvalTier": _approval_tier(
            code,
            dangerous_goods=dangerous_goods,
            sanctions_check=sanctions_check,
        ),
        "riskTags": risk_tags,
        "ownerActor": ACTOR_ID,
        "collection": f"com.etzhayyim.apps.openUnispsc.{level}",
    }
    if segment_name:
        logic["segmentName"] = segment_name
    if total_amount is not None:
        logic["totalAmount"] = total_amount
        logic["currency"] = currency or "USD"

    rec: UnispscRecord = {
        "ok": True,
        "level": level,
        "code": code,
        "name": name or segment_name or code,
        "did": _did(level, code),
        "hierarchy": _hierarchy(code),
        "businessLogic": logic,
        "mcpTool": _tool_name(level),
        "dryRun": dry_run,
        "createdAt": _now_iso(),
    }
    if parent_level and parent_code:
        parent_level_t = parent_level  # help type checkers keep Literal separate
        rec["parentLevel"] = parent_level
        rec["parentCode"] = parent_code
        rec["parentDid"] = _did(parent_level_t, parent_code)  # type: ignore[arg-type]
    return rec


def _error(message: str, level: Level) -> UnispscRecord:
    return {"ok": False, "level": level, "error": message, "mcpTool": _tool_name(level)}


async def _run_graph_for(level: Level, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from kotodama.langgraph_graphs.open_unispsc_pregel import run_open_unispsc
        return await run_open_unispsc(level=level, payload=payload)
    except Exception:
        # Keep MCP tools useful when LangGraph is unavailable in a tiny test
        # environment; the pure business logic remains deterministic.
        code = _norm_code(str(payload.get("code") or ""), level)
        scoped = dict(payload)
        scoped["code"] = code
        return {"ok": True, "results": [dict(record_for_level(level, scoped))]}


async def task_open_unispsc_segment(
    code: str = "",
    name: str = "",
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: segment-level portfolio ownership and governance."""
    try:
        norm = _norm_code(code, "segment")
    except ValueError as exc:
        return _error(str(exc), "segment")
    return await _run_graph_for("segment", {"code": norm, "name": name, "dry_run": dryRun})


async def task_open_unispsc_family(
    code: str = "",
    name: str = "",
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: family-level category-management policy."""
    try:
        norm = _norm_code(code, "family")
    except ValueError as exc:
        return _error(str(exc), "family")
    return await _run_graph_for("family", {"code": norm, "name": name, "dry_run": dryRun})


async def task_open_unispsc_class(
    code: str = "",
    name: str = "",
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: class-level compliance controls."""
    try:
        norm = _norm_code(code, "class")
    except ValueError as exc:
        return _error(str(exc), "class")
    return await _run_graph_for("class", {"code": norm, "name": name, "dry_run": dryRun})


async def task_open_unispsc_commodity(
    code: str = "",
    name: str = "",
    quantity: float | None = None,
    unitPrice: float | None = None,
    currency: str = "USD",
    dangerousGoods: bool = False,
    sanctionsCheck: str = "",
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: commodity-level executable procurement policy."""
    try:
        norm = _norm_code(code, "commodity")
    except ValueError as exc:
        return _error(str(exc), "commodity")
    return await _run_graph_for("commodity", {
        "code": norm,
        "name": name,
        "quantity": quantity,
        "unit_price": unitPrice,
        "currency": currency,
        "dangerous_goods": dangerousGoods,
        "sanctions_check": sanctionsCheck,
        "dry_run": dryRun,
    })


async def task_open_unispsc_design_item(
    commodityCode: str = "",
    commodityName: str = "",
    segment: str = "",
    family: str = "",
    classCode: str = "",
    description: str = "",
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: design an item-specific LangGraph/LangChain contract.

    This uses actual UNSPSC item identity and the existing open-unispsc BPMN
    files as process references.
    """
    try:
        code = _norm_code(commodityCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.designItem"}
    from kotodama.langgraph_graphs.open_unispsc_item import run_item_design

    result = await run_item_design({
        "commodity_code": code,
        "commodity_name": commodityName or code,
        "segment": segment or code[:2],
        "family": family or code[:4],
        "class_code": classCode or code[:6],
        "description": description,
    })
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.designItem"
    return result


async def task_open_unispsc_item_get_spec(
    commodityCode: str = "",
    commodityName: str = "",
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: return an executable item-specific spec contract."""
    try:
        code = _norm_code(commodityCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.itemGetSpec"}
    from kotodama.langgraph_graphs.open_unispsc_item import run_item_operation

    result = await run_item_operation("getSpec", {
        "commodity_code": code,
        "commodity_name": commodityName or code,
    })
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.itemGetSpec"
    return result


async def task_open_unispsc_item_screen_supplier(
    commodityCode: str = "",
    commodityName: str = "",
    supplierDid: str = "",
    legalName: str = "",
    country: str = "",
    kycCleared: bool = False,
    qualityScore: float = 0.0,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: apply supplier.bpmn KYC / quality routing for an item."""
    try:
        code = _norm_code(commodityCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.itemScreenSupplier"}
    from kotodama.langgraph_graphs.open_unispsc_item import run_item_operation

    result = await run_item_operation("screenSupplier", {
        "commodity_code": code,
        "commodity_name": commodityName or code,
        "supplier_did": supplierDid,
        "legal_name": legalName,
        "country": country,
        "kyc_cleared": kycCleared,
        "quality_score": qualityScore,
    })
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.itemScreenSupplier"
    return result


async def task_open_unispsc_item_plan_procurement(
    commodityCode: str = "",
    commodityName: str = "",
    buyerOrgId: str = "",
    quantity: float = 0.0,
    unitPrice: float = 0.0,
    currency: str = "USD",
    dangerousGoods: bool = False,
    sanctionsCheck: str = "",
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: apply procurement.bpmn approval and CAB routing for an item."""
    try:
        code = _norm_code(commodityCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.itemPlanProcurement"}
    from kotodama.langgraph_graphs.open_unispsc_item import run_item_operation

    result = await run_item_operation("planProcurement", {
        "commodity_code": code,
        "commodity_name": commodityName or code,
        "buyer_org_id": buyerOrgId,
        "quantity": quantity,
        "unit_price": unitPrice,
        "currency": currency,
        "dangerous_goods": dangerousGoods,
        "sanctions_check": sanctionsCheck,
    })
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.itemPlanProcurement"
    return result


async def task_open_unispsc_item_flag_compliance(
    commodityCode: str = "",
    commodityName: str = "",
    dualUseCategory: str = "",
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: apply arms / dual-use BPMN references for an item."""
    try:
        code = _norm_code(commodityCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.itemFlagCompliance"}
    from kotodama.langgraph_graphs.open_unispsc_item import run_item_operation

    result = await run_item_operation("flagCompliance", {
        "commodity_code": code,
        "commodity_name": commodityName or code,
        "dual_use_category": dualUseCategory,
    })
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.itemFlagCompliance"
    return result


async def task_open_unispsc_sync_catalog_item(
    commodityCode: str = "",
    commodityName: str = "",
    sourceRepo: str = "",
    rkey: str = "",
    active: bool = True,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: build the okaimono catalog upsert contract for a UNSPSC item."""
    try:
        code = _norm_code(commodityCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.syncCatalogItem"}
    from kotodama.langgraph_graphs.open_unispsc_item import run_item_operation

    result = await run_item_operation("syncCatalogItem", {
        "commodity_code": code,
        "commodity_name": commodityName or code,
        "source_repo": sourceRepo,
        "rkey": rkey,
        "active": active,
    })
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.syncCatalogItem"
    return result


async def task_open_unispsc_plan_catalog_purchase(
    productId: str = "",
    commodityCode: str = "",
    orderId: str = "",
    customerDid: str = "",
    buyerOrgId: str = "",
    quantity: float = 1.0,
    unitPrice: float = 0.0,
    currency: str = "USD",
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: plan okaimono purchase flow for a UNSPSC catalog item."""
    try:
        code = _norm_code(commodityCode, "commodity") if commodityCode else _code_from_product_id(productId)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.planCatalogPurchase"}
    from kotodama.langgraph_graphs.open_unispsc_item import run_item_operation

    result = await run_item_operation("planCatalogPurchase", {
        "commodity_code": code,
        "product_id": productId or f"unispsc-{code}",
        "order_id": orderId,
        "customer_did": customerDid,
        "buyer_org_id": buyerOrgId,
        "quantity": quantity,
        "unit_price": unitPrice,
        "currency": currency,
    })
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.planCatalogPurchase"
    return result


async def task_open_unispsc_sync_all_commodity_dids(
    segmentCodes: list[str] | None = None,
    batchSize: int = 500,
    dryRun: bool = True,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: plan cross-segment commodity DID/profile synchronization."""
    catalog = _load_segments()
    if not catalog:
        return {
            "ok": False,
            "error": f"segments catalog not found: {_segments_csv()}",
            "mcpTool": "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids",
        }
    requested = [str(code) for code in (segmentCodes or [])]
    try:
        codes = [_norm_code(code, "segment") for code in requested] if requested else sorted(catalog)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids"}
    missing = [code for code in codes if code not in catalog]
    if missing:
        return {
            "ok": False,
            "error": f"unknown UNSPSC segment codes: {missing}",
            "mcpTool": "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids",
        }
    safe_batch = max(1, int(batchSize or 500))
    segments = []
    for code in codes:
        row = catalog[code]
        segment_did = f"{OPEN_UNISPSC_DID}:seg{code}"
        segments.append({
            "segment": code,
            "slug": row.get("slug", ""),
            "name": row.get("name", ""),
            "targetActorDid": segment_did,
            "commands": [
                {
                    "command": "register-commodities-bulk",
                    "collection": "com.etzhayyim.apps.unispsc.commodity",
                    "arguments": {"segment": code, "batchSize": safe_batch},
                },
                {
                    "command": "register-commodity-profiles",
                    "didTemplate": f"{OPEN_UNISPSC_DID}:seg{code}:commodity:c{{commodity_code}}",
                    "arguments": {"segment": code, "batchSize": safe_batch},
                },
                {
                    "command": "post-commodity-registration-feed",
                    "actorDid": segment_did,
                    "arguments": {"segment": code},
                },
            ],
        })
    return {
        "ok": True,
        "mcpTool": "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids",
        "dryRun": dryRun,
        "segmentCount": len(segments),
        "batchSize": safe_batch,
        "sourceCatalog": str(_segments_csv().relative_to(_repo_root())),
        "orchestrationPlan": {
            "mode": "cross-actor-fanout",
            "operation": "sync-all-commodity-dids",
            "commandsPerSegment": 3,
            "segments": segments,
        },
    }


async def task_open_unispsc_import_segment_catalog(
    segmentCode: str = "",
    pageSize: int = 1000,
    dryRun: bool = True,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: plan okaimono bulk import for one UNSPSC segment."""
    try:
        segment = _norm_code(segmentCode, "segment")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.importSegmentCatalog"}
    catalog = _load_segments()
    if segment not in catalog:
        return {
            "ok": False,
            "error": f"unknown UNSPSC segment code: {segment}",
            "mcpTool": "com.etzhayyim.apps.openUnispsc.importSegmentCatalog",
        }
    safe_page_size = max(1, int(pageSize or 1000))
    row = catalog[segment]
    return {
        "ok": True,
        "mcpTool": "com.etzhayyim.apps.openUnispsc.importSegmentCatalog",
        "dryRun": dryRun,
        "segment": segment,
        "slug": row.get("slug", ""),
        "name": row.get("name", ""),
        "importCommand": "import-unispsc-segment",
        "sourceQuery": {
            "graph": "unispsc_commodities",
            "where": {"segment": segment},
            "orderBy": ["code"],
            "pageSize": safe_page_size,
        },
        "importPlan": {
            "mode": "bulk-query-to-catalog-upsert",
            "upstreamCollection": "com.etzhayyim.apps.unispsc.commodity",
            "targetRepo": "did:web:okaimono.etzhayyim.com",
            "targetCollection": "com.etzhayyim.apps.okaimono.catalogItem",
            "transformTool": "com.etzhayyim.apps.openUnispsc.syncCatalogItem",
            "idempotencyKey": f"import-unispsc-segment-{segment}",
            "catalogKeyTemplate": "unispsc-{code}",
            "commodityDidTemplate": f"{OPEN_UNISPSC_DID}:seg{segment}:commodity:c{{code}}",
        },
    }


async def task_open_unispsc_supplier(
    supplierDid: str = "",
    commodityCode: str = "",
    legalName: str = "",
    country: str = "",
    kycCleared: bool = False,
    qualityScore: float = 0.0,
    registeredAt: str = "",
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: BPMN-aligned supplier registration and screening."""
    result = await task_open_unispsc_item_screen_supplier(
        commodityCode=commodityCode,
        supplierDid=supplierDid,
        legalName=legalName,
        country=country,
        kycCleared=kycCleared,
        qualityScore=qualityScore,
    )
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.supplier"
    if not result.get("ok"):
        return result
    result["vertexId"] = _vertex_id(
        "com.etzhayyim.apps.openUnispsc.supplier",
        supplierDid,
        result.get("commodityCode", ""),
        registeredAt,
    )
    result["instanceKey"] = _stable_int("open_unispsc_supplier", result["vertexId"])
    result["registeredAt"] = registeredAt or _now_iso()
    status = "blocked" if result.get("riskTier") == "blocked" else "pending-review" if result.get("riskTier") == "manual-review" else "active"
    result["status"] = status
    result["graphWritePlan"] = _graph_write_plan(
        operation="upsertOpenUnispscSupplier",
        rows=[{
            "table": "vertex_open_unispsc_supplier",
            "key": "vertex_id",
            "record": {
                **_base_graph_row(result["registeredAt"]),
                "vertex_id": result["vertexId"],
                "supplier_did": supplierDid,
                "commodity_code": result.get("commodityCode", ""),
                "legal_name": legalName,
                "country": result.get("country", ""),
                "kyc_cleared": result.get("kycCleared", False),
                "quality_score": result.get("qualityScore", 0.0),
                "risk_tier": result.get("riskTier", ""),
                "require_manual_kyc": result.get("requireManualKyc", False),
                "status": status,
                "registered_at": result["registeredAt"],
            },
        }],
    )
    return result


async def task_open_unispsc_procurement(
    buyerOrgId: str = "",
    commodityCode: str = "",
    quantity: float = 0.0,
    unitPrice: float = 0.0,
    currency: str = "USD",
    dangerousGoods: bool = False,
    sanctionsCheck: str = "",
    submittedAt: str = "",
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: BPMN-aligned procurement request planning."""
    result = await task_open_unispsc_item_plan_procurement(
        commodityCode=commodityCode,
        buyerOrgId=buyerOrgId,
        quantity=quantity,
        unitPrice=unitPrice,
        currency=currency,
        dangerousGoods=dangerousGoods,
        sanctionsCheck=sanctionsCheck,
    )
    result["mcpTool"] = "com.etzhayyim.apps.openUnispsc.procurement"
    if not result.get("ok"):
        return result
    result["vertexId"] = _vertex_id(
        "com.etzhayyim.apps.openUnispsc.procurement",
        buyerOrgId,
        result.get("commodityCode", ""),
        submittedAt,
        result.get("totalAmount", 0),
    )
    result["instanceKey"] = _stable_int("open_unispsc_procurement", result["vertexId"])
    result["submittedAt"] = submittedAt or _now_iso()
    code = str(result.get("commodityCode") or "")
    commodity_dst = str(result.get("commodityDst") or _commodity_did(code))
    edge_id = _vertex_id(
        "edge.openUnispsc.procurementCommodity",
        result["vertexId"],
        commodity_dst,
    )
    result["status"] = "submitted"
    result["graphWritePlan"] = _graph_write_plan(
        operation="upsertOpenUnispscProcurement",
        rows=[
            {
                "table": "vertex_open_unispsc_procurement",
                "key": "vertex_id",
                "record": {
                    **_base_graph_row(result["submittedAt"]),
                    "vertex_id": result["vertexId"],
                    "buyer_org_id": buyerOrgId,
                    "commodity_code": code,
                    "quantity": result.get("quantity", 0.0),
                    "unit_price": result.get("unitPrice", 0.0),
                    "currency": result.get("currency", "USD"),
                    "total_amount": result.get("totalAmount", 0.0),
                    "dangerous_goods": result.get("dangerousGoods", False),
                    "sanctions_check": result.get("sanctionsCheck", ""),
                    "approval_tier": result.get("approvalTier", ""),
                    "require_cab": result.get("requireCab", False),
                    "status": "submitted",
                    "submitted_at": result["submittedAt"],
                    "approved_at": "",
                    "settled_at": "",
                },
            },
            {
                "table": "edge_open_unispsc_procurement_commodity",
                "key": "edge_id",
                "record": {
                    **_base_graph_row(result["submittedAt"]),
                    "edge_id": edge_id,
                    "src_vid": result["vertexId"],
                    "dst_vid": commodity_dst,
                    "role": "requests",
                },
            },
        ],
    )
    return result


async def task_open_unispsc_flag_arms_commodity(
    vertexId: str = "",
    commodityVid: str = "",
    unspscCode: str = "",
    subFamily: str = "",
    callerDid: str = "did:web:open-unispsc.etzhayyim.com:ops",
    detectedAt: str = "",
    evidenceUri: str = "",
    confidence: float = 1.0,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: BPMN-aligned UNSPSC segment 46 arms flag."""
    try:
        code = _norm_code(unspscCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.flagArmsCommodity"}
    result = await task_open_unispsc_item_flag_compliance(commodityCode=code, commodityName=subFamily or code)
    is_arms = bool(result.get("arms"))
    commodity_vid = commodityVid or result.get("commodityVid", "")
    event_vid = vertexId or _vertex_id("com.etzhayyim.apps.openDefence.event", "arms", code, commodity_vid, detectedAt)
    timestamp = detectedAt or _now_iso()
    graph_write_plan = _graph_write_plan(
        operation="upsertOpenUnispscArmsDefenceEvent",
        rows=[{
            "table": "vertex_open_defence_event",
            "key": "vertex_id",
            "record": {
                **_base_defence_event_row(timestamp, callerDid),
                "vertex_id": event_vid,
                "bpmn_process_id": "open_unispsc_flag_arms_commodity",
                "nsid": "com.etzhayyim.apps.openUnispsc.flagArmsCommodity",
                "project": "open-unispsc",
                "subject_vid": commodity_vid,
                "action_class": "commodity.arms",
                "severity": "high",
                "commodity_code": code,
                "evidence_uri": evidenceUri,
                "confidence": confidence,
            },
        }],
    )
    return {
        "ok": is_arms,
        "vertexId": event_vid,
        "commodityVid": commodity_vid,
        "unspscCode": code,
        "subFamily": subFamily,
        "bpmnProcessId": "open_unispsc_flag_arms_commodity",
        "instanceKey": _stable_int("open_unispsc_flag_arms_commodity", event_vid, commodity_vid, code),
        "auditAction": "commodity.arms",
        "graphWritePlan": graph_write_plan,
        "mcpTool": "com.etzhayyim.apps.openUnispsc.flagArmsCommodity",
        **({} if is_arms else {"error": "UNSPSC arms flag requires segment 46 commodity code"}),
    }


async def task_open_unispsc_flag_dual_use_commodity(
    vertexId: str = "",
    commodityVid: str = "",
    unspscCode: str = "",
    dualUseCategory: str = "",
    callerDid: str = "did:web:open-unispsc.etzhayyim.com:ops",
    detectedAt: str = "",
    evidenceUri: str = "",
    confidence: float = 1.0,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: BPMN-aligned dual-use commodity flag."""
    try:
        code = _norm_code(unspscCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.flagDualUseCommodity"}
    result = await task_open_unispsc_item_flag_compliance(
        commodityCode=code,
        commodityName=dualUseCategory or code,
        dualUseCategory=dualUseCategory,
    )
    is_dual_use = bool(result.get("dualUse"))
    commodity_vid = commodityVid or result.get("commodityVid", "")
    event_vid = vertexId or _vertex_id("com.etzhayyim.apps.openDefence.event", "dualUse", code, commodity_vid, dualUseCategory, detectedAt)
    timestamp = detectedAt or _now_iso()
    graph_write_plan = _graph_write_plan(
        operation="upsertOpenUnispscDualUseDefenceEvent",
        rows=[{
            "table": "vertex_open_defence_event",
            "key": "vertex_id",
            "record": {
                **_base_defence_event_row(timestamp, callerDid),
                "vertex_id": event_vid,
                "bpmn_process_id": "open_unispsc_flag_dual_use_commodity",
                "nsid": "com.etzhayyim.apps.openUnispsc.flagDualUseCommodity",
                "project": "open-unispsc",
                "subject_vid": commodity_vid,
                "action_class": "commodity.dualUse",
                "severity": "high",
                "commodity_code": code,
                "evidence_uri": evidenceUri,
                "confidence": confidence,
            },
        }],
    )
    return {
        "ok": is_dual_use,
        "vertexId": event_vid,
        "commodityVid": commodity_vid,
        "unspscCode": code,
        "dualUseCategory": dualUseCategory,
        "bpmnProcessId": "open_unispsc_flag_dual_use_commodity",
        "instanceKey": _stable_int("open_unispsc_flag_dual_use_commodity", event_vid, commodity_vid, code, dualUseCategory),
        "auditAction": "openUnispsc.commodity.flagDualUse",
        "graphWritePlan": graph_write_plan,
        "mcpTool": "com.etzhayyim.apps.openUnispsc.flagDualUseCommodity",
        **({} if is_dual_use else {"error": "UNSPSC dual-use flag requires a dual-use category or regulated segment"}),
    }


async def task_open_unispsc_apply_graph_write_plan(
    graphWritePlan: dict[str, Any] | None = None,
    dryRun: bool = True,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: validate or apply an openUnispsc graphWritePlan.

    The default dry-run path is intentionally pure so callers can ask the MCP
    tool to prove table/column/key compatibility before handing work to a DB
    writer.  Set dryRun=false to execute the validated statements.
    """
    rows, errors = _validate_graph_write_plan(graphWritePlan or {})
    statements = [_statement_preview(*_sql_for_graph_row(row)) for row in rows]
    if errors:
        return {
            "ok": False,
            "dryRun": dryRun,
            "mcpTool": "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan",
            "errors": errors,
            "validatedRows": len(rows),
            "sqlStatements": statements,
        }

    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "mcpTool": "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan",
            "appliedRows": 0,
            "validatedRows": len(rows),
            "sqlStatements": statements,
        }

    try:
        pass
    except Exception as exc:
        return {
            "ok": False,
            "dryRun": False,
            "mcpTool": "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan",
            "error": f"db_sync unavailable: {exc}",
            "validatedRows": len(rows),
            "sqlStatements": statements,
        }

    applied = 0
    if True:
        client = get_kotoba_client()
        for stmt in statements:
            _res = client.q(stmt["sql"], stmt["parameters"])
            applied += 1
    return {
        "ok": True,
        "dryRun": False,
        "mcpTool": "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan",
        "appliedRows": applied,
        "validatedRows": len(rows),
        "sqlStatements": statements,
    }


async def task_open_unispsc_run_item_workflow(
    commodityCode: str = "",
    commodityName: str = "",
    supplierDid: str = "",
    legalName: str = "",
    country: str = "",
    kycCleared: bool = False,
    qualityScore: float = 0.0,
    buyerOrgId: str = "",
    quantity: float = 0.0,
    unitPrice: float = 0.0,
    currency: str = "USD",
    dangerousGoods: bool = False,
    sanctionsCheck: str = "",
    dualUseCategory: str = "",
    callerDid: str = "did:web:open-unispsc.etzhayyim.com:ops",
    eventAt: str = "",
    evidenceUri: str = "",
    confidence: float = 1.0,
    **_: Any,
) -> dict[str, Any]:
    """MCP tool: run the full item-level UNSPSC procurement workflow."""
    try:
        code = _norm_code(commodityCode, "commodity")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "mcpTool": "com.etzhayyim.apps.openUnispsc.runItemWorkflow"}

    timestamp = eventAt or _now_iso()
    spec = await task_open_unispsc_item_get_spec(commodityCode=code, commodityName=commodityName or code)
    supplier = await task_open_unispsc_supplier(
        supplierDid=supplierDid,
        commodityCode=code,
        legalName=legalName,
        country=country,
        kycCleared=kycCleared,
        qualityScore=qualityScore,
        registeredAt=timestamp,
    )
    procurement = await task_open_unispsc_procurement(
        buyerOrgId=buyerOrgId,
        commodityCode=code,
        quantity=quantity,
        unitPrice=unitPrice,
        currency=currency,
        dangerousGoods=dangerousGoods,
        sanctionsCheck=sanctionsCheck,
        submittedAt=timestamp,
    )
    compliance = await task_open_unispsc_item_flag_compliance(
        commodityCode=code,
        commodityName=commodityName or code,
        dualUseCategory=dualUseCategory,
    )

    commodity_vid = _commodity_did(code)
    arms = None
    if compliance.get("arms"):
        arms = await task_open_unispsc_flag_arms_commodity(
            commodityVid=commodity_vid,
            unspscCode=code,
            subFamily=commodityName or code,
            callerDid=callerDid,
            detectedAt=timestamp,
            evidenceUri=evidenceUri,
            confidence=confidence,
        )
    dual_use = None
    if compliance.get("dualUse"):
        dual_use = await task_open_unispsc_flag_dual_use_commodity(
            commodityVid=commodity_vid,
            unspscCode=code,
            dualUseCategory=dualUseCategory or "regulated-unspsc-segment",
            callerDid=callerDid,
            detectedAt=timestamp,
            evidenceUri=evidenceUri,
            confidence=confidence,
        )

    graph_write_plan = _merge_graph_write_plans(
        "upsertOpenUnispscItemWorkflow",
        supplier.get("graphWritePlan"),
        procurement.get("graphWritePlan"),
        arms.get("graphWritePlan") if isinstance(arms, dict) else None,
        dual_use.get("graphWritePlan") if isinstance(dual_use, dict) else None,
    )
    validated_rows, validation_errors = _validate_graph_write_plan(graph_write_plan)
    supplier_tier = supplier.get("riskTier", "")
    workflow_status = (
        "blocked" if supplier_tier == "blocked"
        else "manual-review" if supplier_tier == "manual-review" or procurement.get("requireCab")
        else "ready"
    )
    return {
        "ok": not validation_errors and all(step.get("ok") for step in [spec, supplier, procurement, compliance]),
        "mcpTool": "com.etzhayyim.apps.openUnispsc.runItemWorkflow",
        "workflowStatus": workflow_status,
        "commodityCode": code,
        "commodityName": commodityName or code,
        "steps": {
            "spec": spec,
            "supplier": supplier,
            "procurement": procurement,
            "compliance": compliance,
            **({"arms": arms} if arms else {}),
            **({"dualUse": dual_use} if dual_use else {}),
        },
        "summary": {
            "supplierRiskTier": supplier_tier,
            "approvalTier": procurement.get("approvalTier", ""),
            "requireCab": procurement.get("requireCab", False),
            "arms": bool(compliance.get("arms")),
            "dualUse": bool(compliance.get("dualUse")),
            "defenceEventCount": int(bool(arms)) + int(bool(dual_use)),
        },
        "graphWritePlan": graph_write_plan,
        "graphWriteValidation": {
            "ok": not validation_errors,
            "validatedRows": len(validated_rows),
            "errors": validation_errors,
        },
    }


async def task_open_unispsc_coverage_snapshot(**_: Any) -> dict[str, Any]:
    """MCP tool: report openUnispsc contract/handler/BPMN/graph coverage."""
    lexicon_dir = _lexicon_dir()
    bpmn_dir = _bpmn_contract_dir()
    seed_sql_path = _mcp_seed_sql()
    down_sql_path = _mcp_seed_down_sql()
    alembic_path = _mcp_alembic_wrapper()
    try:
        seed_sql = seed_sql_path.read_text(encoding="utf-8")
        seed_error = ""
    except Exception as exc:
        seed_sql = ""
        seed_error = str(exc)
    try:
        down_sql = down_sql_path.read_text(encoding="utf-8")
        down_error = ""
    except Exception as exc:
        down_sql = ""
        down_error = str(exc)
    try:
        alembic_wrapper = alembic_path.read_text(encoding="utf-8")
        alembic_error = ""
    except Exception as exc:
        alembic_wrapper = ""
        alembic_error = str(exc)
    try:
        from kotodama.mcp_dispatch import build_actor_handlers
        handlers = build_actor_handlers({"openUnispsc"})
        dispatcher_error = ""
    except Exception as exc:  # pragma: no cover - defensive
        handlers = {}
        dispatcher_error = str(exc)

    tools = []
    missing: list[str] = []
    for spec in _EXPECTED_TOOL_SPECS:
        lexicon_path = lexicon_dir / str(spec["lexicon"])
        nsid = str(spec["nsid"])
        bpmn_status = {
            bpmn: (bpmn_dir / bpmn).exists()
            for bpmn in spec.get("bpmn", [])
        }
        graph_status = {
            target: target in _GRAPH_TABLES
            for target in spec.get("graphTargets", [])
        }
        handler_fn_name = f"task_open_unispsc_{_snake_method(str(spec['method']))}"
        lexicon_present = lexicon_path.exists()
        entry = {
            "method": spec["method"],
            "nsid": nsid,
            "handlerFunction": handler_fn_name,
            "handlerFunctionPresent": callable(globals().get(handler_fn_name)),
            "handlerRegistered": nsid in handlers,
            "lexiconPath": str(lexicon_path.relative_to(_repo_root())),
            "lexiconPresent": lexicon_present,
            "lexiconValid": lexicon_present and _lexicon_json_valid(lexicon_path, nsid),
            "seedRegistered": nsid in seed_sql,
            "downRegistered": nsid in down_sql,
            "bpmnPresent": bpmn_status,
            "graphTargetsAllowed": graph_status,
        }
        if not entry["handlerFunctionPresent"]:
            missing.append(f"handlerFunction:{handler_fn_name}")
        if not entry["handlerRegistered"]:
            missing.append(f"handler:{nsid}")
        if not entry["lexiconPresent"]:
            missing.append(f"lexicon:{spec['lexicon']}")
        if entry["lexiconPresent"] and not entry["lexiconValid"]:
            missing.append(f"lexiconInvalid:{spec['lexicon']}")
        if not entry["seedRegistered"]:
            missing.append(f"seed:{nsid}")
        if not entry["downRegistered"]:
            missing.append(f"down:{nsid}")
        missing.extend(f"bpmn:{name}" for name, ok in bpmn_status.items() if not ok)
        missing.extend(f"graphTarget:{name}" for name, ok in graph_status.items() if not ok)
        tools.append(entry)

    alembic_references_up = seed_sql_path.name in alembic_wrapper
    alembic_references_down = down_sql_path.name in alembic_wrapper
    if alembic_error:
        missing.append("alembic:wrapper")
    if not alembic_references_up:
        missing.append("alembic:up")
    if not alembic_references_down:
        missing.append("alembic:down")

    return {
        "ok": not missing and not dispatcher_error and not seed_error and not down_error and not alembic_error,
        "mcpTool": "com.etzhayyim.apps.openUnispsc.coverageSnapshot",
        "toolCount": len(tools),
        "graphTargetCount": len(_GRAPH_TABLES),
        "bpmnDir": str(bpmn_dir.relative_to(_repo_root())),
        "lexiconDir": str(lexicon_dir.relative_to(_repo_root())),
        "seedSqlPath": str(seed_sql_path.relative_to(_repo_root())),
        "downSqlPath": str(down_sql_path.relative_to(_repo_root())),
        "alembicPath": str(alembic_path.relative_to(_repo_root())),
        "alembicPresent": not alembic_error,
        "alembicReferencesUpSql": alembic_references_up,
        "alembicReferencesDownSql": alembic_references_down,
        "tools": tools,
        "graphTargets": sorted(_GRAPH_TABLES.keys()),
        "missing": sorted(set(missing)),
        **({"dispatcherError": dispatcher_error} if dispatcher_error else {}),
        **({"seedError": seed_error} if seed_error else {}),
        **({"downError": down_error} if down_error else {}),
        **({"alembicError": alembic_error} if alembic_error else {}),
    }


def record_for_level(level: Level, payload: dict[str, Any]) -> UnispscRecord:
    code = _norm_code(str(payload.get("code") or ""), level)
    return _record(
        level=level,
        code=code,
        name=str(payload.get("name") or ""),
        dry_run=bool(payload.get("dry_run") or payload.get("dryRun")),
        quantity=payload.get("quantity"),
        unit_price=payload.get("unit_price"),
        currency=str(payload.get("currency") or "USD"),
        dangerous_goods=bool(payload.get("dangerous_goods")),
        sanctions_check=str(payload.get("sanctions_check") or ""),
    )


def hierarchy_records(level: Level, payload: dict[str, Any]) -> list[UnispscRecord]:
    code = _norm_code(str(payload.get("code") or ""), level)
    requested_index = ["segment", "family", "class", "commodity"].index(level)
    records: list[UnispscRecord] = []
    for current in ["segment", "family", "class", "commodity"][: requested_index + 1]:
        current_level = current  # type: ignore[assignment]
        current_code = code[: _LEVEL_DIGITS[current_level]]  # type: ignore[index]
        scoped = dict(payload)
        scoped["code"] = current_code
        if current != level:
            scoped["name"] = ""
        records.append(record_for_level(current_level, scoped))  # type: ignore[arg-type]
    return records


async def smoke_call(level: Level, code: str) -> dict[str, Any]:
    """Small helper used by tests and local smoke scripts."""
    fn = {
        "segment": task_open_unispsc_segment,
        "family": task_open_unispsc_family,
        "class": task_open_unispsc_class,
        "commodity": task_open_unispsc_commodity,
    }[level]
    return await fn(code=code, dryRun=True)


def stable_vertex_id(level: Level, code: str) -> str:
    digest = hashlib.sha256(f"{level}:{code}".encode("utf-8")).hexdigest()[:24]
    return f"at://{OPEN_UNISPSC_DID}/com.etzhayyim.apps.openUnispsc.{level}/{digest}"


def smoke_call_sync(level: Level, code: str) -> dict[str, Any]:
    return asyncio.run(smoke_call(level, code))

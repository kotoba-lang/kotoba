"""UNSPSC item-specific LangGraph + LangChain design graph.

This graph is for actual UNSPSC items (for example 25172504 Vehicle Batteries),
not just hierarchy grains.  It uses the existing open-unispsc BPMN files as
reference process contracts and emits a per-item execution design that can be
turned into concrete tools, prompts, or generated components.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, TypedDict

try:
    from langchain_core.prompts import ChatPromptTemplate
except Exception:  # pragma: no cover
    ChatPromptTemplate = None  # type: ignore[assignment]

try:
    from langgraph.graph import END, StateGraph
    _LANGGRAPH_OK = True
except ImportError:  # pragma: no cover
    END = "END"  # type: ignore[assignment]
    StateGraph = object  # type: ignore[assignment]
    _LANGGRAPH_OK = False


class OpenUnispscItemState(TypedDict, total=False):
    commodity_code: str
    commodity_name: str
    segment: str
    family: str
    class_code: str
    description: str
    bpmn_refs: list[dict[str, Any]]
    risk_profile: dict[str, Any]
    langchain_prompt: dict[str, Any]
    langgraph_design: dict[str, Any]
    operation: str
    tool_result: dict[str, Any]
    supplier_did: str
    legal_name: str
    country: str
    kyc_cleared: bool
    quality_score: float
    buyer_org_id: str
    quantity: float
    unit_price: float
    currency: str
    dangerous_goods: bool
    sanctions_check: str
    dual_use_category: str
    source_repo: str
    rkey: str
    active: bool
    product_id: str
    order_id: str
    customer_did: str
    ok: bool
    error: str


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "00-contracts").exists() and (parent / "60-apps").exists():
            return parent
    return here.parents[6]


def _bpmn_dir() -> Path:
    return _repo_root() / "00-contracts/bpmn/com/etzhayyim/open-unispsc"


def _clean_code(value: Any, digits: int) -> str:
    code = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(code) != digits:
        raise ValueError(f"expected {digits}-digit UNSPSC code")
    return code


def normalize_item(state: OpenUnispscItemState) -> dict[str, Any]:
    try:
        code = _clean_code(state.get("commodity_code") or state.get("commodityCode"), 8)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "commodity_code": code,
        "segment": state.get("segment") or code[:2],
        "family": state.get("family") or code[:4],
        "class_code": state.get("class_code") or state.get("classCode") or code[:6],
        "commodity_name": str(state.get("commodity_name") or state.get("commodityName") or code),
    }


def _parse_bpmn(path: Path) -> dict[str, Any]:
    ns = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "zeebe": "http://camunda.org/schema/zeebe/1.0",
    }
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    process = root.find("bpmn:process", ns)
    tasks = []
    for task in root.findall(".//bpmn:serviceTask", ns):
        task_def = task.find(".//zeebe:taskDefinition", ns)
        tasks.append({
            "id": task.attrib.get("id", ""),
            "name": task.attrib.get("name", ""),
            "type": task_def.attrib.get("type", "") if task_def is not None else "",
        })
    return {
        "sourcePath": str(path.relative_to(_repo_root())),
        "processId": process.attrib.get("id", "") if process is not None else "",
        "name": process.attrib.get("name", "") if process is not None else "",
        "serviceTasks": tasks,
    }


def load_bpmn_refs(state: OpenUnispscItemState) -> dict[str, Any]:
    refs = [_parse_bpmn(p) for p in sorted(_bpmn_dir().glob("*.bpmn"))]
    segment = state.get("segment", "")
    selected = []
    for ref in refs:
        pid = ref["processId"]
        if pid in {"open_unispsc_procurement", "open_unispsc_supplier"}:
            selected.append(ref)
        elif segment == "46" and pid == "open_unispsc_flag_arms_commodity":
            selected.append(ref)
        elif pid == "open_unispsc_flag_dual_use_commodity" and segment in {"12", "26", "32", "41", "46", "51"}:
            selected.append(ref)
    return {"bpmn_refs": selected}


def infer_item_risk(state: OpenUnispscItemState) -> dict[str, Any]:
    code = state.get("commodity_code", "")
    name = state.get("commodity_name", "")
    haystack = f"{code} {name}".lower()
    risks: list[str] = []
    if state.get("segment") == "46":
        risks.append("arms-or-security")
    if state.get("segment") in {"12", "51"}:
        risks.append("regulated-material")
    if re.search(r"battery|lithium|chemical|explosive|radio|laser|weapon|firearm|drug|pharma", haystack):
        risks.append("specialized-compliance")
    if state.get("segment", "00") >= "70":
        risks.append("service-delivery")
    return {
        "risk_profile": {
            "tags": risks,
            "approval": "cab-review" if risks else "standard-procurement",
            "requiresSupplierScreen": True,
            "requiresProcurementFlow": True,
        }
    }


def build_langchain_prompt(state: OpenUnispscItemState) -> dict[str, Any]:
    system = (
        "You design item-specific UNSPSC procurement agents. "
        "Use the BPMN references as process contracts and return concise JSON."
    )
    user = (
        "UNSPSC {commodity_code} {commodity_name}; segment={segment}, "
        "family={family}, class={class_code}. BPMN refs={bpmn_refs}. "
        "Risk profile={risk_profile}. Design item-specific tools, checks, "
        "approval gates, and evidence fields."
    )
    if ChatPromptTemplate is not None:
        prompt = ChatPromptTemplate.from_messages([("system", system), ("human", user)])
        messages = [
            {"role": getattr(m, "type", ""), "content": m.content}
            for m in prompt.format_messages(**state)
        ]
    else:
        messages = [
            {"role": "system", "content": system},
            {"role": "human", "content": user.format(**state)},
        ]
    return {
        "langchain_prompt": {
            "framework": "langchain",
            "template": "ChatPromptTemplate",
            "messages": messages,
            "outputContract": {
                "tools": "item-specific MCP/LangGraph callable tools",
                "checks": "validation and compliance checks",
                "evidenceFields": "facts persisted or audited per BPMN",
            },
        }
    }


def build_item_graph_design(state: OpenUnispscItemState) -> dict[str, Any]:
    code = state.get("commodity_code", "")
    nsid_prefix = f"com.etzhayyim.apps.openUnispsc.item{code}"
    bpmn_ids = [r["processId"] for r in state.get("bpmn_refs", [])]
    nodes = [
        "normalize_item",
        "load_bpmn_refs",
        "infer_item_risk",
        "draft_item_spec",
        "supplier_screen",
        "procurement_plan",
        "catalog_sync_plan",
        "purchase_flow_plan",
        "audit_binding",
    ]
    if "open_unispsc_flag_arms_commodity" in bpmn_ids:
        nodes.insert(-1, "arms_control_gate")
    if "open_unispsc_flag_dual_use_commodity" in bpmn_ids:
        nodes.insert(-1, "dual_use_gate")
    return {
        "langgraph_design": {
            "framework": "langgraph",
            "graphId": f"open_unispsc_item_{code}",
            "commodityCode": code,
            "commodityName": state.get("commodity_name", ""),
            "nodes": nodes,
            "edges": [[nodes[i], nodes[i + 1]] for i in range(len(nodes) - 1)],
            "mcpTools": {
                "design": "com.etzhayyim.apps.openUnispsc.designItem",
                "getSpec": "com.etzhayyim.apps.openUnispsc.itemGetSpec",
                "screenSupplier": "com.etzhayyim.apps.openUnispsc.itemScreenSupplier",
                "planProcurement": "com.etzhayyim.apps.openUnispsc.itemPlanProcurement",
                "flagCompliance": "com.etzhayyim.apps.openUnispsc.itemFlagCompliance",
                "syncCatalogItem": "com.etzhayyim.apps.openUnispsc.syncCatalogItem",
                "planCatalogPurchase": "com.etzhayyim.apps.openUnispsc.planCatalogPurchase",
                "itemScopedPrefix": nsid_prefix,
            },
            "bpmnReferences": state.get("bpmn_refs", []),
            "riskProfile": state.get("risk_profile", {}),
        }
    }


def draft_item_spec(state: OpenUnispscItemState) -> dict[str, Any]:
    design = build_item_graph_design(state)["langgraph_design"]
    prompt = build_langchain_prompt(state)["langchain_prompt"]
    code = state.get("commodity_code", "")
    name = state.get("commodity_name", "")
    return {
        "tool_result": {
            "ok": True,
            "operation": "getSpec",
            "commodityCode": code,
            "commodityName": name,
            "hierarchy": {
                "segment": state.get("segment", ""),
                "family": state.get("family", ""),
                "class": state.get("class_code", ""),
                "commodity": code,
            },
            "did": f"did:web:unispsc.etzhayyim.com:seg{code[:2]}:commodity:c{code}",
            "specTemplate": {
                "identity": ["commodityCode", "commodityName", "segment", "family", "class"],
                "commercial": ["quantity", "unit", "currency", "unitPrice", "leadTimeDays"],
                "quality": ["standards", "certifications", "inspectionCriteria"],
                "risk": ["dangerousGoods", "sanctionsCheck", "countryOfOrigin", "supplierRiskTier"],
            },
            "langgraphDesign": design,
            "langchainPrompt": prompt,
            "bpmnReferences": state.get("bpmn_refs", []),
        }
    }


def screen_supplier(state: OpenUnispscItemState) -> dict[str, Any]:
    country = str(state.get("country") or "").upper()
    quality = float(state.get("quality_score", 0.0) or 0.0)
    kyc = bool(state.get("kyc_cleared", False))
    if country in {"IRN", "PRK", "RUS", "SYR", "MMR"}:
        risk_tier = "blocked"
    elif quality < 0.5 or not kyc:
        risk_tier = "manual-review"
    elif quality >= 0.7 and kyc:
        risk_tier = "approved"
    else:
        risk_tier = "manual-review"
    return {
        "tool_result": {
            "ok": True,
            "operation": "screenSupplier",
            "commodityCode": state.get("commodity_code", ""),
            "supplierDid": state.get("supplier_did", ""),
            "legalName": state.get("legal_name", ""),
            "country": country,
            "kycCleared": kyc,
            "qualityScore": quality,
            "riskTier": risk_tier,
            "requireManualKyc": quality < 0.7 or not kyc,
            "bpmnProcessId": "open_unispsc_supplier",
            "auditAction": f"openUnispsc.supplier.{risk_tier.replace('-', '')}",
            "bpmnReferences": [
                r for r in state.get("bpmn_refs", [])
                if r.get("processId") == "open_unispsc_supplier"
            ],
        }
    }


def plan_procurement(state: OpenUnispscItemState) -> dict[str, Any]:
    quantity = float(state.get("quantity", 0.0) or 0.0)
    unit_price = float(state.get("unit_price", 0.0) or 0.0)
    total = quantity * unit_price
    dangerous = bool(state.get("dangerous_goods", False))
    if total >= 1_000_000 or dangerous:
        approval_tier = "enterprise"
    elif total >= 50_000:
        approval_tier = "department"
    else:
        approval_tier = "routine"
    return {
        "tool_result": {
            "ok": True,
            "operation": "planProcurement",
            "commodityCode": state.get("commodity_code", ""),
            "buyerOrgId": state.get("buyer_org_id", ""),
            "quantity": quantity,
            "unitPrice": unit_price,
            "currency": state.get("currency") or "USD",
            "totalAmount": total,
            "dangerousGoods": dangerous,
            "sanctionsCheck": state.get("sanctions_check", ""),
            "approvalTier": approval_tier,
            "requireCab": approval_tier == "enterprise",
            "commodityDst": f"did:web:unispsc.etzhayyim.com:seg{state.get('commodity_code', '')[:2]}:commodity:c{state.get('commodity_code', '')}",
            "bpmnProcessId": "open_unispsc_procurement",
            "auditAction": "openUnispsc.procurement.cabRequest" if approval_tier == "enterprise" else "openUnispsc.procurement.autoApprove",
            "bpmnReferences": [
                r for r in state.get("bpmn_refs", [])
                if r.get("processId") == "open_unispsc_procurement"
            ],
        }
    }


def flag_compliance(state: OpenUnispscItemState) -> dict[str, Any]:
    code = state.get("commodity_code", "")
    segment = state.get("segment", "")
    tags = state.get("risk_profile", {}).get("tags", [])
    is_arms = segment == "46" or "arms-or-security" in tags
    is_dual_use = (
        bool(state.get("dual_use_category"))
        or segment in {"12", "26", "32", "41", "46", "51"}
        or "specialized-compliance" in tags
    )
    refs = []
    if is_arms:
        refs.extend(r for r in state.get("bpmn_refs", []) if r.get("processId") == "open_unispsc_flag_arms_commodity")
    if is_dual_use:
        refs.extend(r for r in state.get("bpmn_refs", []) if r.get("processId") == "open_unispsc_flag_dual_use_commodity")
    return {
        "tool_result": {
            "ok": True,
            "operation": "flagCompliance",
            "commodityCode": code,
            "commodityVid": f"did:web:unispsc.etzhayyim.com:seg{code[:2]}:commodity:c{code}",
            "arms": is_arms,
            "dualUse": is_dual_use,
            "dualUseCategory": state.get("dual_use_category", ""),
            "severity": "high" if (is_arms or is_dual_use) else "none",
            "bpmnProcessIds": [r.get("processId") for r in refs],
            "bpmnReferences": refs,
        }
    }


def sync_catalog_item(state: OpenUnispscItemState) -> dict[str, Any]:
    code = state.get("commodity_code", "")
    name = state.get("commodity_name", "") or code
    product_id = f"unispsc-{code}"
    segment = state.get("segment", "")
    family = state.get("family", "")
    class_code = state.get("class_code", "")
    commodity_did = f"did:web:unispsc.etzhayyim.com:seg{segment}:commodity:c{code}"
    source_repo = state.get("source_repo", "") or "did:web:unispsc.etzhayyim.com"
    rkey = state.get("rkey", "") or code
    active = bool(state.get("active", True))
    record = {
        "product_id": product_id,
        "sku": f"UNSPSC-{code}",
        "title": name,
        "category": f"unispsc:{segment}:{family}:{class_code}",
        "unispsc_code": code,
        "unispsc_segment": segment,
        "unispsc_family": family,
        "unispsc_class": class_code,
        "commodity_did": commodity_did,
        "active": active,
    }
    return {
        "tool_result": {
            "ok": True,
            "operation": "syncCatalogItem",
            "commodityCode": code,
            "commodityName": name,
            "sourceCollection": "com.etzhayyim.apps.unispsc.commodity",
            "sourceRepo": source_repo,
            "sourceRkey": rkey,
            "catalogCollection": "com.etzhayyim.apps.okaimono.catalogItem",
            "catalogRkey": product_id,
            "catalogItem": record,
            "atprotoWritePlan": {
                "mode": "deterministic-upsert",
                "operation": "upsertOkaimonoCatalogItemFromUnispscCommodity",
                "repo": "did:web:okaimono.etzhayyim.com",
                "collection": "com.etzhayyim.apps.okaimono.catalogItem",
                "rkey": product_id,
                "record": record,
            },
            "classificationEdge": {
                "src": f"at://did:web:okaimono.etzhayyim.com/com.etzhayyim.apps.okaimono.catalogItem/{product_id}",
                "dst": commodity_did,
                "role": "CLASSIFIED_BY",
            },
        }
    }


def plan_catalog_purchase(state: OpenUnispscItemState) -> dict[str, Any]:
    code = state.get("commodity_code", "")
    product_id = state.get("product_id", "") or f"unispsc-{code}"
    quantity = float(state.get("quantity", 1.0) or 1.0)
    unit_price = float(state.get("unit_price", 0.0) or 0.0)
    currency = state.get("currency", "") or "USD"
    segment_actor = f"did:web:unispsc.etzhayyim.com:seg{code[:2]}"
    order_id = state.get("order_id", "")
    buyer_org_id = state.get("buyer_org_id", "")
    return {
        "tool_result": {
            "ok": True,
            "operation": "planCatalogPurchase",
            "productId": product_id,
            "commodityCode": code,
            "commodityDid": f"did:web:unispsc.etzhayyim.com:seg{code[:2]}:commodity:c{code}",
            "orderLine": {
                "orderId": order_id,
                "productId": product_id,
                "quantity": quantity,
                "unitPrice": unit_price,
                "currency": currency,
            },
            "checkoutSaga": {
                "sagaId": "chk8uty2",
                "step": "order-create",
                "buyerOrgId": buyer_org_id,
                "customerDid": state.get("customer_did", ""),
            },
            "procurementInvocation": {
                "step": "procurement-find-offers",
                "targetActorDid": segment_actor,
                "mcpTool": "com.etzhayyim.apps.openUnispsc.itemGetSpec",
                "arguments": {"commodityCode": code},
            },
            "fulfillmentPlan": {
                "step": "fulfillment-create-shipment",
                "requiresSpec": True,
                "requiresOffer": True,
            },
            "purchaseFlow": [
                "catalog-search",
                "order-create",
                "checkout-saga",
                "procurement-find-offers",
                "item-get-spec",
                "fulfillment-create-shipment",
            ],
        }
    }


def finalize(state: OpenUnispscItemState) -> dict[str, Any]:
    return {"ok": not bool(state.get("error"))}


def _build():
    builder = StateGraph(OpenUnispscItemState)
    builder.add_node("normalize_item", normalize_item)
    builder.add_node("load_bpmn_refs", load_bpmn_refs)
    builder.add_node("infer_item_risk", infer_item_risk)
    builder.add_node("build_langchain_prompt", build_langchain_prompt)
    builder.add_node("build_item_graph_design", build_item_graph_design)
    builder.add_node("finalize", finalize)
    builder.set_entry_point("normalize_item")
    builder.add_edge("normalize_item", "load_bpmn_refs")
    builder.add_edge("load_bpmn_refs", "infer_item_risk")
    builder.add_edge("infer_item_risk", "build_langchain_prompt")
    builder.add_edge("build_langchain_prompt", "build_item_graph_design")
    builder.add_edge("build_item_graph_design", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()


def build_graph():
    if not _LANGGRAPH_OK:
        return None
    return _build()


def _build_operation(operation: str):
    node_by_operation = {
        "getSpec": draft_item_spec,
        "screenSupplier": screen_supplier,
        "planProcurement": plan_procurement,
        "flagCompliance": flag_compliance,
        "syncCatalogItem": sync_catalog_item,
        "planCatalogPurchase": plan_catalog_purchase,
    }
    if operation not in node_by_operation:
        raise ValueError(f"unsupported item operation: {operation}")
    builder = StateGraph(OpenUnispscItemState)
    builder.add_node("normalize_item", normalize_item)
    builder.add_node("load_bpmn_refs", load_bpmn_refs)
    builder.add_node("infer_item_risk", infer_item_risk)
    builder.add_node(operation, node_by_operation[operation])
    builder.add_node("finalize", finalize)
    builder.set_entry_point("normalize_item")
    builder.add_edge("normalize_item", "load_bpmn_refs")
    builder.add_edge("load_bpmn_refs", "infer_item_risk")
    builder.add_edge("infer_item_risk", operation)
    builder.add_edge(operation, "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()


async def run_item_design(payload: dict[str, Any]) -> dict[str, Any]:
    if not _LANGGRAPH_OK:
        state: OpenUnispscItemState = dict(payload)
        for fn in [normalize_item, load_bpmn_refs, infer_item_risk, build_langchain_prompt, build_item_graph_design, finalize]:
            state.update(fn(state))
        return dict(state)
    graph = _build()
    return dict(await graph.ainvoke(payload))


async def run_item_operation(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _LANGGRAPH_OK:
        state: OpenUnispscItemState = dict(payload)
        for fn in [normalize_item, load_bpmn_refs, infer_item_risk]:
            state.update(fn(state))
        op_fn = {
            "getSpec": draft_item_spec,
            "screenSupplier": screen_supplier,
            "planProcurement": plan_procurement,
            "flagCompliance": flag_compliance,
            "syncCatalogItem": sync_catalog_item,
            "planCatalogPurchase": plan_catalog_purchase,
        }[operation]
        state.update(op_fn(state))
        state.update(finalize(state))
        return dict(state.get("tool_result") or state)
    graph = _build_operation(operation)
    result = dict(await graph.ainvoke(payload))
    return dict(result.get("tool_result") or result)

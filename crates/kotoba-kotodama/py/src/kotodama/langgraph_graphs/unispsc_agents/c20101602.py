from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class SteelProcurementState(TypedDict):
    material_spec: Dict[str, Any]
    certification_verified: bool
    compliance_risk: List[str]
    approved: bool

def validate_material_specs(state: SteelProcurementState):
    spec = state.get("material_spec", {})
    verified = "cert_standard" in spec and spec["tensile_strength"] > 0
    return {"certification_verified": verified}

def risk_assessment(state: SteelProcurementState):
    risks = []
    if state.get("material_spec", {}).get("dual_use", False):
        risks.append("dual-use-export-control")
    return {"compliance_risk": risks}

def approval_node(state: SteelProcurementState):
    is_approved = state["certification_verified"] and len(state["compliance_risk"]) == 0
    return {"approved": is_approved}

graph = StateGraph(SteelProcurementState)
graph.add_node("validate", validate_material_specs)
graph.add_node("risk", risk_assessment)
graph.add_node("approve", approval_node)
graph.set_entry_point("validate")
graph.add_edge("validate", "risk")
graph.add_edge("risk", "approve")
graph.add_edge("approve", END)
graph = graph.compile()

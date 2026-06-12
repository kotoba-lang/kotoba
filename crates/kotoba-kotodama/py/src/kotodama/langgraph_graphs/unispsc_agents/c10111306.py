from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class ProcureState(TypedDict):
    commodity_id: str
    validation_checks: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_machinery_specs(state: ProcureState) -> dict:
    checks = ["check_tonnage_rating", "verify_safety_compliance"]
    return {"validation_checks": checks}

def check_procurement_risk(state: ProcureState) -> dict:
    # Logic for high-value risk assessment
    return {"is_approved": True}

graph = StateGraph(ProcureState)
graph.add_node("validate", validate_machinery_specs)
graph.add_node("risk_assessment", check_procurement_risk)
graph.add_edge("validate", "risk_assessment")
graph.add_edge("risk_assessment", END)
graph.set_entry_point("validate")
graph = graph.compile()

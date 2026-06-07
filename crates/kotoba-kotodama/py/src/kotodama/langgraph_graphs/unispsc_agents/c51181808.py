from langgraph.graph import StateGraph, END
from typing import TypedDict
class ProcurementState(TypedDict):
    commodity: str
    quality_check: bool
    compliant: bool
def validate_purity(state: ProcurementState):
    return {"quality_check": True}
def check_compliance(state: ProcurementState):
    return {"compliant": state.get("quality_check", False)}
graph = StateGraph(ProcurementState)
graph.add_node("purity_check", validate_purity)
graph.add_node("safety_compliance", check_compliance)
graph.set_entry_point("purity_check")
graph.add_edge("purity_check", "safety_compliance")
graph.add_edge("safety_compliance", END)
graph = graph.compile()

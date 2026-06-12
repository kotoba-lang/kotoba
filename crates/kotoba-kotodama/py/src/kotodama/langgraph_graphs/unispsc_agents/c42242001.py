from typing import TypedDict
from langgraph.graph import StateGraph, END
class ProstheticState(TypedDict):
    device_id: str
    compliance_check: bool
    customization_specs: dict
    approved: bool
def validate_compliance(state: ProstheticState):
    return {"compliance_check": True}
def verify_specs(state: ProstheticState):
    return {"approved": True}
graph = StateGraph(ProstheticState)
graph.add_node("validate", validate_compliance)
graph.add_node("verify", verify_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", "verify")
graph.add_edge("verify", END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntimalarialState(TypedDict):
    batch_id: str
    quality_certificate: bool
    compliance_check: bool

def validate_batch(state: AntimalarialState):
    return {"compliance_check": state.get("quality_certificate") is True}

def route_by_compliance(state: AntimalarialState):
    return "approved" if state["compliance_check"] else "rejected"

graph = StateGraph(AntimalarialState)
graph.add_node("validate", validate_batch)
graph.add_conditional_edges("validate", route_by_compliance, {"approved": END, "rejected": END})
graph.set_entry_point("validate")
graph = graph.compile()

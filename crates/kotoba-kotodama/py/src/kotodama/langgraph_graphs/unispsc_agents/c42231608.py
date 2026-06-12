from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    compliance_cleared: bool
    quality_score: float

def validate_medical_device(state: ProcurementState):
    # Business logic for medical device procurement validation
    if state.get("item_id").startswith("JST"):
        return {"compliance_cleared": True}
    return {"compliance_cleared": False}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_medical_device)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

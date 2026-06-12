from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    blade_material: str
    safety_check: bool

def validate_safety(state: ProcurementState):
    state["safety_check"] = state.get("blade_material") != "unprotected_thin_sheet"
    return state

def finalize_order(state: ProcurementState):
    return {"status": "validated" if state["safety_check"] else "rejected"}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_safety)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

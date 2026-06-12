from langgraph.graph import StateGraph, END
from typing import TypedDict
class GearState(TypedDict):
    material: str
    spec_check: bool
    validation_log: list
    is_approved: bool
def validate_specs(state: GearState) -> GearState:
    if state.get("material") in ["Steel", "Bronze"]:
        state["spec_check"] = True
        state["validation_log"].append("Material conforms to industrial standards.")
    else:
        state["spec_check"] = False
    return state
def approval_step(state: GearState) -> GearState:
    state["is_approved"] = state["spec_check"]
    return state
graph = StateGraph(GearState)
graph.add_node("validate", validate_specs)
graph.add_node("approve", approval_step)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()

from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class LockState(TypedDict):
    lock_id: str
    security_rating: str
    approval_status: bool
    validation_errors: List[str]

def validate_specs(state: LockState):
    errors = []
    if not state.get("security_rating"): errors.append("Missing rating")
    return {"validation_errors": errors, "approval_status": len(errors) == 0}

def route_by_validation(state: LockState):
    return "approved" if state["approval_status"] else "rejected"

graph = StateGraph(LockState)
graph.add_node("validate", validate_specs)
graph.add_conditional_edges("validate", route_by_validation, {"approved": END, "rejected": END})
graph.set_entry_point("validate")
graph = graph.compile()

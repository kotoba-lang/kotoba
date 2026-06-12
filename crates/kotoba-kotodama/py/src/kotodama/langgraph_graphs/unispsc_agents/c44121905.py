from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class InkPadState(TypedDict):
    product_name: str
    ink_type: str
    dry_time_seconds: int
    is_compliant: bool

def validate_spec(state: InkPadState):
    """Validate that ink pads meet office supply standards."""
    if state.get("ink_type") in ["oil-based", "water-based"]:
        state["is_compliant"] = True
    else:
        state["is_compliant"] = False
    return state

def check_dry_time(state: InkPadState):
    """Ensure drying time is within document safety limits."""
    if state.get("dry_time_seconds", 0) > 300:
        state["is_compliant"] = False
    return state

graph = StateGraph(InkPadState)
graph.add_node("validate", validate_spec)
graph.add_node("dry_check", check_dry_time)
graph.add_edge("validate", "dry_check")
graph.add_edge("dry_check", END)
graph.set_entry_point("validate")
graph = graph.compile()

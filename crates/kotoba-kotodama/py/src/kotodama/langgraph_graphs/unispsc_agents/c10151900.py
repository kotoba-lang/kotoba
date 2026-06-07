from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class LivestockState(TypedDict):
    commodity_id: str
    validation_checks: Annotated[list[str], operator.add]
    is_approved: bool

def validate_livestock_supply(state: LivestockState):
    checks = []
    if state.get("commodity_id"):
        checks.append("ID_FORMAT_VALID")
    return {"validation_checks": checks}

def approval_node(state: LivestockState):
    approved = len(state["validation_checks"]) > 0
    return {"is_approved": approved}

graph = StateGraph(LivestockState)
graph.add_node("validate", validate_livestock_supply)
graph.add_node("approve", approval_node)
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph.set_entry_point("validate")
graph = graph.compile()

from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    supply_id: str
    validation_checks: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_supply(state: LivestockState) -> LivestockState:
    checks = ["check_origin", "verify_health_cert"]
    return {"validation_checks": checks, "is_compliant": True}

def update_inventory(state: LivestockState) -> LivestockState:
    return {"is_compliant": True}

graph = StateGraph(LivestockState)
graph.add_node("validate", validate_supply)
graph.add_node("inventory", update_inventory)
graph.add_edge("validate", "inventory")
graph.add_edge("inventory", END)
graph.set_entry_point("validate")
graph = graph.compile()

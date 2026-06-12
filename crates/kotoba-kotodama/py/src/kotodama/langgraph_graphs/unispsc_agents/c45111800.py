from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AVSystemState(TypedDict):
    equipment_list: List[str]
    validation_checks: List[str]
    is_approved: bool

def validate_hardware(state: AVSystemState):
    checks = ["check_connectivity", "check_power", "check_resolution"]
    return {"validation_checks": checks, "is_approved": True}

def route_procurement(state: AVSystemState):
    return "end_node" if state["is_approved"] else "reject_node"

graph = StateGraph(AVSystemState)
graph.add_node("validate", validate_hardware)
graph.add_edge("validate", END)
graph.set_entry_point("validate")
graph = graph.compile()

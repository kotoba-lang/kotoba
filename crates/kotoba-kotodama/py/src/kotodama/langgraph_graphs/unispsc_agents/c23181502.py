from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotPartState(TypedDict):
    part_id: str
    spec_check: bool
    is_dual_use: bool

def validate_specs(state: RobotPartState):
    # Simulate CAD and material compliance check
    return {"spec_check": True}

def check_export_controls(state: RobotPartState):
    # Business logic for dual-use threshold
    return {"is_dual_use": False}

graph = StateGraph(RobotPartState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", check_export_controls)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()

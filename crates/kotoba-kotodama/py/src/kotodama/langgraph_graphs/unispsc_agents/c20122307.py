from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MotionControlState(TypedDict):
    part_number: str
    specs_verified: bool
    compliance_checked: bool
    final_procurement_data: dict

def validate_specs(state: MotionControlState):
    # Simulate validation logic for high-precision motor controllers
    state["specs_verified"] = True
    return state

def check_export_compliance(state: MotionControlState):
    # Logic for dual-use technology check
    state["compliance_checked"] = True
    return state

graph = StateGraph(MotionControlState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", check_export_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()

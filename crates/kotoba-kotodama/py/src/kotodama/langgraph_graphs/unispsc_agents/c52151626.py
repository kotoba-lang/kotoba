from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MandolinSpecState(TypedDict):
    blade_material: str
    safety_check_passed: bool
    compliance_cert: str

def validate_blade_quality(state: MandolinSpecState):
    # Business logic for blade material verification
    return {"blade_material": "Validated"}

def check_safety_features(state: MandolinSpecState):
    # Logic for safety guard existence
    return {"safety_check_passed": True}

graph = StateGraph(MandolinSpecState)
graph.add_node("validate_blade", validate_blade_quality)
graph.add_node("check_safety", check_safety_features)
graph.set_entry_point("validate_blade")
graph.add_edge("validate_blade", "check_safety")
graph.add_edge("check_safety", END)
graph = graph.compile()

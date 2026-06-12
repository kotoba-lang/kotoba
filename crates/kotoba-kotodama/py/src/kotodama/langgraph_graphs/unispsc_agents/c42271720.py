from langgraph.graph import StateGraph, END
from typing import TypedDict

class ConverterState(TypedDict):
    pressure_vessel_valid: bool
    cryogenic_safety_passed: bool
    final_clearance: bool

def validate_vessel(state: ConverterState):
    return {"pressure_vessel_valid": True}

def validate_safety(state: ConverterState):
    return {"cryogenic_safety_passed": True}

def finalize(state: ConverterState):
    return {"final_clearance": state["pressure_vessel_valid"] and state["cryogenic_safety_passed"]}

graph = StateGraph(ConverterState)
graph.add_node("validate_vessel", validate_vessel)
graph.add_node("validate_safety", validate_safety)
graph.add_node("finalize", finalize)
graph.set_entry_point("validate_vessel")
graph.add_edge("validate_vessel", "validate_safety")
graph.add_edge("validate_safety", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class VacuumSupplyState(TypedDict):
    part_code: str
    compatibility_verified: bool
    inspection_passed: bool

def validate_part(state: VacuumSupplyState):
    # Simulate verification of vacuum part compatibility
    return {"compatibility_verified": True}

def perform_quality_check(state: VacuumSupplyState):
    # Simulate physical QC inspection logic
    return {"inspection_passed": True}

graph = StateGraph(VacuumSupplyState)
graph.add_node("validate", validate_part)
graph.add_node("qc", perform_quality_check)
graph.add_edge("validate", "qc")
graph.add_edge("qc", END)
graph.set_entry_point("validate")

graph = graph.compile()

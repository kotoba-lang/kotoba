from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    tolerance_check: bool
    load_test_results: dict
    approved: bool

def validate_tolerance(state: BearingState):
    # Simulate CAD/Tolerance validation logic
    return {"tolerance_check": True}

def perform_load_test(state: BearingState):
    # Simulate physical inspection workflow
    return {"load_test_results": {"status": "pass"}, "approved": True}

graph = StateGraph(BearingState)
graph.add_node("validate", validate_tolerance)
graph.add_node("test", perform_load_test)
graph.add_edge("validate", "test")
graph.add_edge("test", END)
graph.set_entry_point("validate")
graph = graph.compile()

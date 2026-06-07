from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_id: str
    tolerance_validation: bool
    load_verification: bool
    is_compliant: bool

def validate_tolerance(state: BearingState):
    # Simulate geometric dimensioning and tolerancing check
    return {"tolerance_validation": True}

def verify_load(state: BearingState):
    # Simulate load rating verification against spec
    return {"load_verification": True}

def finalize_check(state: BearingState):
    compliant = state["tolerance_validation"] and state["load_verification"]
    return {"is_compliant": compliant}

graph = StateGraph(BearingState)
graph.add_node("tolerance", validate_tolerance)
graph.add_node("load", verify_load)
graph.add_node("final", finalize_check)

graph.set_entry_point("tolerance")
graph.add_edge("tolerance", "load")
graph.add_edge("load", "final")
graph.add_edge("final", END)

graph = graph.compile()

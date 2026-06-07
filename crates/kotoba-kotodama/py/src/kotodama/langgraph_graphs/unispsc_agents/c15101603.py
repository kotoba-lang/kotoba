from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    material_certified: bool
    tolerance_check_passed: bool
    load_validation: bool

def validate_material(state: BearingState) -> dict:
    return {"material_certified": True}

def check_tolerance(state: BearingState) -> dict:
    return {"tolerance_check_passed": True}

def finalize_validation(state: BearingState) -> dict:
    return {"load_validation": True}

graph = StateGraph(BearingState)
graph.add_node("material", validate_material)
graph.add_node("tolerance", check_tolerance)
graph.add_node("load", finalize_validation)
graph.set_entry_point("material")
graph.add_edge("material", "tolerance")
graph.add_edge("tolerance", "load")
graph.add_edge("load", END)
graph = graph.compile()

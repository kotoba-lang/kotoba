from typing import TypedDict
from langgraph.graph import StateGraph, END

class PuzzleState(TypedDict):
    material_certified: bool
    safety_passed: bool
    dimensions_verified: bool

def validate_materials(state: PuzzleState):
    return {'material_certified': True}

def check_safety(state: PuzzleState):
    return {'safety_passed': True}

def verify_dimensions(state: PuzzleState):
    return {'dimensions_verified': True}

graph = StateGraph(PuzzleState)
graph.add_node("MaterialCheck", validate_materials)
graph.add_node("SafetyCheck", check_safety)
graph.add_node("DimensionCheck", verify_dimensions)
graph.set_entry_point("MaterialCheck")
graph.add_edge("MaterialCheck", "SafetyCheck")
graph.add_edge("SafetyCheck", "DimensionCheck")
graph.add_edge("DimensionCheck", END)
graph = graph.compile()

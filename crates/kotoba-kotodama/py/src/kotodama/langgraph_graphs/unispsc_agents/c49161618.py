from typing import TypedDict
from langgraph.graph import StateGraph, END

class TetherBallState(TypedDict):
    material_certified: bool
    tensile_strength_check: bool
    approved: bool

def validate_material(state: TetherBallState):
    return {"material_certified": True}

def validate_tensile(state: TetherBallState):
    return {"tensile_strength_check": True}

def decision_node(state: TetherBallState):
    state["approved"] = state["material_certified"] and state["tensile_strength_check"]
    return state

graph = StateGraph(TetherBallState)
graph.add_node("validate_material", validate_material)
graph.add_node("validate_tensile", validate_tensile)
graph.add_node("finalize", decision_node)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "validate_tensile")
graph.add_edge("validate_tensile", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

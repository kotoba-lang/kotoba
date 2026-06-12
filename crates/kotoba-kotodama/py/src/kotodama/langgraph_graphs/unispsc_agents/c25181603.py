from typing import TypedDict
from langgraph.graph import StateGraph, END

class FrameState(TypedDict):
    frame_id: str
    material_certified: bool
    geometry_valid: bool
    status: str

def validate_material(state: FrameState):
    # Simulate material composition validation
    return {"material_certified": True}

def validate_geometry(state: FrameState):
    # Simulate CAD dimension checking
    return {"geometry_valid": True}

def finalize_check(state: FrameState):
    if state["material_certified"] and state["geometry_valid"]:
        return {"status": "APPROVED"}
    return {"status": "REJECTED"}

graph = StateGraph(FrameState)
graph.add_node("validate_material", validate_material)
graph.add_node("validate_geometry", validate_geometry)
graph.add_node("finalize", finalize_check)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "validate_geometry")
graph.add_edge("validate_geometry", "finalize")
graph.add_edge("finalize", END)

graph = graph.compile()

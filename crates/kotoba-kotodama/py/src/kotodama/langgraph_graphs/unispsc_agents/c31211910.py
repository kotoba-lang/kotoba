from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PaintToolState(TypedDict):
    material: str
    solvent_ready: bool
    is_approved: bool

def validate_material(state: PaintToolState):
    # Simulate material compliance check
    return {"is_approved": state.get("material") in ["polyester", "microfiber"]}

def finalize_order(state: PaintToolState):
    return {"is_approved": True}

graph = StateGraph(PaintToolState)
graph.add_node("validate", validate_material)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

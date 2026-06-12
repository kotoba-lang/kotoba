from typing import TypedDict
from langgraph.graph import StateGraph, END
class AssemblyState(TypedDict):
    assembly_id: str
    material_check: bool
    weld_integrity_score: float
    status: str
def check_material(state: AssemblyState):
    return {"material_check": True}
def validate_weld(state: AssemblyState):
    return {"weld_integrity_score": 0.95, "status": "verified"}
graph = StateGraph(AssemblyState)
graph.add_node("check_material", check_material)
graph.add_node("validate_weld", validate_weld)
graph.set_entry_point("check_material")
graph.add_edge("check_material", "validate_weld")
graph.add_edge("validate_weld", END)
graph = graph.compile()

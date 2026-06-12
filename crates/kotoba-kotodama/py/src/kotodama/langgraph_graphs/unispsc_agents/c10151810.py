from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    component_id: str
    material_specs: dict
    inspection_status: str
    is_approved: bool

def validate_materials(state: MiningState) -> dict:
    # Logic to check material compliance
    return {"inspection_status": "PASSED", "is_approved": True}

def prepare_logistics(state: MiningState) -> dict:
    return {"inspection_status": "LOGISTICS_READY"}

graph = StateGraph(MiningState)
graph.add_node("validate", validate_materials)
graph.add_node("logistics", prepare_logistics)
graph.add_edge("validate", "logistics")
graph.add_edge("logistics", END)
graph.set_entry_point("validate")
graph = graph.compile()

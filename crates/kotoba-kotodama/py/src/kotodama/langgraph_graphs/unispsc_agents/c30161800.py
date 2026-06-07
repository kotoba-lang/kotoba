from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CabinetState(TypedDict):
    material_certified: bool
    blueprint_validated: bool
    quality_score: float

def validate_materials(state: CabinetState):
    return {"material_certified": True}

def validate_blueprints(state: CabinetState):
    return {"blueprint_validated": True}

builder = StateGraph(CabinetState)
builder.add_node("validate_materials", validate_materials)
builder.add_node("validate_blueprints", validate_blueprints)
builder.set_entry_point("validate_materials")
builder.add_edge("validate_materials", "validate_blueprints")
builder.add_edge("validate_blueprints", END)
graph = builder.compile()

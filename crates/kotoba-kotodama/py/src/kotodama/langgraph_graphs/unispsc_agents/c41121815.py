from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabComponentState(TypedDict):
    component_id: str
    pressure_rating: float
    material_compliance: bool
    is_approved: bool

def validate_material(state: LabComponentState):
    # Simulate material compliance check for lab fittings
    return {"material_compliance": state.get("material_compliance", True)}

def check_pressure(state: LabComponentState):
    # Validate psi requirements for laboratory vacuum/gas lines
    is_ok = state.get("pressure_rating", 0) > 0
    return {"is_approved": is_ok}

graph = StateGraph(LabComponentState)
graph.add_node("validate_material", validate_material)
graph.add_node("check_pressure", check_pressure)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "check_pressure")
graph.add_edge("check_pressure", END)
graph = graph.compile()

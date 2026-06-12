from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalFlaskState(TypedDict):
    flask_id: str
    material_certified: bool
    thermal_test_passed: bool

def validate_materials(state: DentalFlaskState):
    return {"material_certified": True}

def perform_thermal_analysis(state: DentalFlaskState):
    return {"thermal_test_passed": True}

graph = StateGraph(DentalFlaskState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("thermal_analysis", perform_thermal_analysis)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "thermal_analysis")
graph.add_edge("thermal_analysis", END)
graph = graph.compile()

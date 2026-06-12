from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class OilPanState(TypedDict):
    part_number: str
    material_certified: bool
    pressure_test_passed: bool
    final_approval: bool

def validate_material(state: OilPanState):
    # Simulate material compliance check
    return {"material_certified": True}

def validate_pressure(state: OilPanState):
    # Simulate pressure leakage testing
    return {"pressure_test_passed": True}

def finalize_qc(state: OilPanState):
    return {"final_approval": state["material_certified"] and state["pressure_test_passed"]}

graph = StateGraph(OilPanState)
graph.add_node("check_material", validate_material)
graph.add_node("check_pressure", validate_pressure)
graph.add_node("finalize", finalize_qc)

graph.set_entry_point("check_material")
graph.add_edge("check_material", "check_pressure")
graph.add_edge("check_pressure", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

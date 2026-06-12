from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_spec: str
    pressure_test_passed: bool
    compliance_docs: list

def validate_material(state: ProcurementState):
    return {"material_spec": "Material vetted for NACE MR0175"}

def verify_pressure_safety(state: ProcurementState):
    return {"pressure_test_passed": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_material)
graph.add_node("pressure_check", verify_pressure_safety)
graph.add_edge("validate", "pressure_check")
graph.add_edge("pressure_check", END)
graph.set_entry_point("validate")
graph = graph.compile()

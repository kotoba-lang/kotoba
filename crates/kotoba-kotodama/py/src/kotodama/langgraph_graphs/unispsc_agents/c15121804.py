from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class AlloyProcurementState(TypedDict):
    part_number: str
    material_spec: str
    compliance_checks: List[str]
    is_approved: bool

def validate_material(state: AlloyProcurementState):
    # Simulate CAD/Spec validation for aerospace alloy
    checks = state.get("compliance_checks", [])
    if "as9100" in [c.lower() for c in checks]:
        return {"is_approved": True}
    return {"is_approved": False}

workflow = StateGraph(AlloyProcurementState)
workflow.add_node("validate", validate_material)
workflow.set_entry_point("validate")
workflow.add_edge("validate", END)

graph = workflow.compile()

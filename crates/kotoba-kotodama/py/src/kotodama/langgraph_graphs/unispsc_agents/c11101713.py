from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class ProcurementState(TypedDict):
    material_id: str
    quality_docs: list[str]
    compliance_checks: Annotated[list[str], operator.add]
    is_approved: bool

def validate_material_specs(state: ProcurementState):
    # Simulated technical validation for aerospace grade alloys
    return {"compliance_checks": ["composition_verified", "particle_size_ok"]}

def security_export_review(state: ProcurementState):
    # Dual-use review logic
    return {"is_approved": True}

workflow = StateGraph(ProcurementState)
workflow.add_node("validate", validate_material_specs)
workflow.add_node("export_review", security_export_review)
workflow.add_edge("validate", "export_review")
workflow.add_edge("export_review", END)
workflow.set_entry_point("validate")
graph = workflow.compile()

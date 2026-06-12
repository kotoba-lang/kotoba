from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SiCState(TypedDict):
    purity_check: bool
    particle_validation: bool
    export_license_status: str
    final_decision: str

def validate_purity(state: SiCState):
    # Simulate stringent purity check for semiconductor grade SiC
    return {"purity_check": True}

def validate_particle_size(state: SiCState):
    # Simulate particle distribution verification
    return {"particle_validation": True}

def assess_export_control(state: SiCState):
    # Dual-use assessment logic
    return {"export_license_status": "APPROVED_FOR_INTERNAL_SEMICONDUCTOR_FAB"}

workflow = StateGraph(SiCState)
workflow.add_node("purity", validate_purity)
workflow.add_node("particle", validate_particle_size)
workflow.add_node("export", assess_export_control)

workflow.set_entry_point("purity")
workflow.add_edge("purity", "particle")
workflow.add_edge("particle", "export")
workflow.add_edge("export", END)

graph = workflow.compile()

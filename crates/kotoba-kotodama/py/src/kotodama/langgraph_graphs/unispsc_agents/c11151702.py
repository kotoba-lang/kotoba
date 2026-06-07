from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MetalProcurementState(TypedDict):
    material_id: str
    purity_check: bool
    compliance_risk: List[str]
    spec_validation: bool

def validate_purity(state: MetalProcurementState) -> MetalProcurementState:
    # Logic to verify material purity against standards
    state['purity_check'] = True
    return state

def check_compliance(state: MetalProcurementState) -> MetalProcurementState:
    # Check for dual-use or sanction risks
    state['compliance_risk'] = ['dual-use-export-control']
    return state

workflow = StateGraph(MetalProcurementState)
workflow.add_node('validate', validate_purity)
workflow.add_node('compliance', check_compliance)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'compliance')
workflow.add_edge('compliance', END)
graph = workflow.compile()

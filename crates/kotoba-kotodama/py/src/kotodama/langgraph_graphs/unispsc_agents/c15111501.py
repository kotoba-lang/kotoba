from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AluminumProcurementState(TypedDict):
    material_code: str
    purity_level: float
    inspection_passed: bool
    compliance_tags: List[str]

def validate_material_specs(state: AluminumProcurementState) -> AluminumProcurementState:
    # Logic for validating aerospace-grade aluminium alloy specifications
    if state.get('purity_level', 0) >= 99.9:
        state['inspection_passed'] = True
        state['compliance_tags'].append('aerospace_ready')
    else:
        state['inspection_passed'] = False
    return state

def route_for_security_review(state: AluminumProcurementState) -> str:
    return 'process_order' if state['inspection_passed'] else 'flag_for_review'

workflow = StateGraph(AluminumProcurementState)
workflow.add_node('validate', validate_material_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)

graph = workflow.compile()

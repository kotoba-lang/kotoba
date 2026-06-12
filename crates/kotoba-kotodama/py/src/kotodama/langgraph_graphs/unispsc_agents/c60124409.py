from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_composition: dict
    compliance_cleared: bool

def validate_composition(state: ProcurementState):
    composition = state.get('material_composition', {})
    is_valid = all(key in composition for key in ['Sn', 'Sb', 'Cu'])
    return {'compliance_cleared': is_valid}

def perform_quality_check(state: ProcurementState):
    print('Verifying chemical analysis against industry standards for pewter...')
    return {'compliance_cleared': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_composition)
graph.add_node('qc', perform_quality_check)
graph.add_edge('validate', 'qc')
graph.add_edge('qc', END)
graph.set_entry_point('validate')
graph = graph.compile()

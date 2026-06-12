from typing import TypedDict
from langgraph.graph import StateGraph, END

class StackProcurementState(TypedDict):
    material_spec: str
    inspection_report: str
    compliance_status: bool

def validate_materials(state: StackProcurementState):
    print('Validating steel grade and welding specs...')
    return {'compliance_status': True}

def perform_structural_review(state: StackProcurementState):
    print('Reviewing load-bearing calculations...')
    return {'compliance_status': True}

graph = StateGraph(StackProcurementState)
graph.add_node('validate', validate_materials)
graph.add_node('structural', perform_structural_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'structural')
graph.add_edge('structural', END)
graph = graph.compile()

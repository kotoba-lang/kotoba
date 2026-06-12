from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool
    procurement_action: str

def validate_dipper_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    required = ['material', 'capacity']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def route_procurement(state: ProcurementState):
    return 'approve' if state['validation_passed'] else 'request_revision'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_dipper_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_procurement, {'approve': END, 'request_revision': END})
graph = graph.compile()

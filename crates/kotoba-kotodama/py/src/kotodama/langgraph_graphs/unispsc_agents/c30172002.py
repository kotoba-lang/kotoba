from typing import TypedDict
from langgraph.graph import StateGraph, END

class GateProcurementState(TypedDict):
    gate_spec: dict
    validation_results: list
    is_approved: bool

def validate_gate_spec(state: GateProcurementState):
    specs = state.get('gate_spec', {})
    errors = []
    if 'material' not in specs: errors.append('Missing material')
    if 'dimensions' not in specs: errors.append('Missing dimensions')
    return {'validation_results': errors, 'is_approved': len(errors) == 0}

def route_verification(state: GateProcurementState):
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(GateProcurementState)
graph.add_node('validate', validate_gate_spec)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_verification, {'approved': END, 'rejected': END})
graph = graph.compile()

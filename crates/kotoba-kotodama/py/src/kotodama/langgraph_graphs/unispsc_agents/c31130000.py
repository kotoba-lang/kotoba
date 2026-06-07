from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    spec_data: dict
    validation_status: str
    is_approved: bool

def validate_specs(state: ForgingState):
    specs = state.get('spec_data', {})
    # Logic to verify tensile strength and NDT certification
    is_valid = all(k in specs for k in ['tensile_strength', 'ndt_report'])
    return {'validation_status': 'passed' if is_valid else 'failed', 'is_approved': is_valid}

def route_by_validation(state: ForgingState):
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(ForgingState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation, {'approved': END, 'rejected': END})
graph = graph.compile()

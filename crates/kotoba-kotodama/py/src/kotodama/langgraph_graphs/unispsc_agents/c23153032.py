from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingGraphState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: WeldingGraphState):
    specs = state.get('spec_data', {})
    valid = 'payload_capacity_kg' in specs and 'safety_certification_standards' in specs
    return {'validated': valid, 'error_log': [] if valid else ['Missing mandatory specs']}

def approval_check(state: WeldingGraphState):
    return 'approved' if state['validated'] else 'rejected'

graph = StateGraph(WeldingGraphState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', approval_check, {'approved': END, 'rejected': END})
graph = graph.compile()

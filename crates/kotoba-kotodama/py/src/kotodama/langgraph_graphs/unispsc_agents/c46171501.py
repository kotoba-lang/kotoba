from typing import TypedDict
from langgraph.graph import StateGraph, END

class LockState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_specs(state: LockState):
    specs = state.get('spec_data', {})
    state['is_compliant'] = 'security_grade_level' in specs
    return state

def route_by_compliance(state: LockState):
    return 'process_order' if state['is_compliant'] else 'request_revision'

graph = StateGraph(LockState)
graph.add_node('validate', validate_specs)
graph.add_node('process_order', lambda s: s)
graph.add_node('request_revision', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process_order', END)
graph.add_edge('request_revision', END)

graph = graph.compile()

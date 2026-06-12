from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SilkscreenState(TypedDict):
    spec_requirements: dict
    validation_status: bool
    error_logs: List[str]

def validate_specs(state: SilkscreenState):
    specs = state.get('spec_requirements', {})
    errors = []
    if 'mesh_count' not in specs: errors.append('Missing mesh count')
    if 'registration_tolerance' not in specs: errors.append('Missing registration tolerance')
    return {'validation_status': len(errors) == 0, 'error_logs': errors}

def approval_step(state: SilkscreenState):
    return {'validation_status': True} if state.get('validation_status') else {'validation_status': False}

graph = StateGraph(SilkscreenState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

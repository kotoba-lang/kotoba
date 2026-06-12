from typing import TypedDict
from langgraph.graph import StateGraph, END

class FiberState(TypedDict):
    spec_data: dict
    valid: bool
    error_log: list

def validate_specs(state: FiberState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('AttenuationLoss', 0) > 0.5:
        errors.append('Attenuation loss exceeds threshold')
    return {'valid': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: FiberState):
    return 'process' if state['valid'] else END

graph = StateGraph(FiberState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()

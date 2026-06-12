from typing import TypedDict
from langgraph.graph import StateGraph, END

class ComponentState(TypedDict):
    spec_data: dict
    validation_status: bool
    error_log: list

def validate_specs(state: ComponentState):
    specs = state.get('spec_data', {})
    required = ['material_grade', 'tolerance']
    valid = all(key in specs for key in required)
    return {'validation_status': valid, 'error_log': [] if valid else ['Missing specs']}

def route_by_validation(state: ComponentState):
    return 'process' if state['validation_status'] else END

graph = StateGraph(ComponentState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda s: {'validation_status': True})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()

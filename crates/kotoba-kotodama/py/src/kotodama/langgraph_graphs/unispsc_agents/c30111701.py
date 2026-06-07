from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlasterState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_plaster_specs(state: PlasterState):
    specs = state.get('spec_data', {})
    required = ['compressive_strength_mpa', 'setting_time_minutes']
    valid = all(key in specs for key in required) and specs.get('setting_time_minutes', 0) > 0
    return {'validation_result': valid}

def route_by_validation(state: PlasterState):
    return 'process' if state['validation_result'] else END

graph = StateGraph(PlasterState)
graph.add_node('validate', validate_plaster_specs)
graph.add_node('process', lambda s: {'validation_result': True})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class SensorState(TypedDict):
    spec_data: dict
    validated: bool
    error: str

def validate_specs(state: SensorState):
    specs = state.get('spec_data', {})
    required = ['operating_temp', 'voltage']
    if all(k in specs for k in required):
        return {'validated': True}
    return {'validated': False, 'error': 'Missing required technical specs'}

def route_by_validation(state: SensorState):
    return 'validate' if not state.get('validated') else END

graph = StateGraph(SensorState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

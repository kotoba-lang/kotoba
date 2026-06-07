from typing import TypedDict
from langgraph.graph import StateGraph, END

class LightingState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_induction_specs(state: LightingState):
    specs = state.get('spec_data', {})
    required = ['luminous_flux', 'ip_rating']
    state['validation_passed'] = all(k in specs for k in required)
    return state

def process_procurement(state: LightingState):
    print('Processing induction lighting procurement workflow.')
    return state

graph = StateGraph(LightingState)
graph.add_node('validate', validate_induction_specs)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

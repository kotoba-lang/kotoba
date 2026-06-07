from typing import TypedDict
from langgraph.graph import StateGraph, END

class LugState(TypedDict):
    part_number: str
    material: str
    gauge: str
    is_compliant: bool

def validate_specs(state: LugState) -> LugState:
    # Simulate spec validation logic
    state['is_compliant'] = state.get('material') in ['copper', 'aluminum']
    return state

def check_gauge(state: LugState) -> LugState:
    # Validate wire range
    print(f'Checking gauge: {state.get('gauge')}')
    return state

graph = StateGraph(LugState)
graph.add_node('validate', validate_specs)
graph.add_node('gauge_check', check_gauge)
graph.set_entry_point('validate')
graph.add_edge('validate', 'gauge_check')
graph.add_edge('gauge_check', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class SmokerState(TypedDict):
    temp_range: str
    material_certified: bool
    compliance_checked: bool

def validate_specs(state: SmokerState):
    state['compliance_checked'] = state.get('material_certified', False) and 'deg' in state.get('temp_range', '')
    return state

graph = StateGraph(SmokerState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

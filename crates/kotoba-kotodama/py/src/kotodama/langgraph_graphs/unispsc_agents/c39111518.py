from typing import TypedDict
from langgraph.graph import StateGraph, END

class LightSpecState(TypedDict):
    spec_data: dict
    is_valid: bool

def validate_spec(state: LightSpecState):
    specs = state.get('spec_data', {})
    # Check for mandatory technical requirements
    is_valid = 'IP Rating' in specs and 'Lumen Output' in specs
    return {'is_valid': is_valid}

def approve_procurement(state: LightSpecState):
    print('Approval flow initiated for light fixture.')
    return {}

graph = StateGraph(LightSpecState)
graph.add_node('validate', validate_spec)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

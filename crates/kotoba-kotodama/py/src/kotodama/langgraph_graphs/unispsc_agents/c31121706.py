from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    specs: dict
    validated: bool
    error: str

def validate_casting_specs(state: CastingState):
    s = state.get('specs', {})
    # Logic for checking aluminum casting tolerance and alloy standards
    is_valid = 'alloy' in s and 'tolerance' in s
    return {'validated': is_valid, 'error': '' if is_valid else 'Missing specs'}

def route_by_validation(state: CastingState):
    return 'validate' if not state.get('validated') else END

graph = StateGraph(CastingState)
graph.add_node('validate', validate_casting_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

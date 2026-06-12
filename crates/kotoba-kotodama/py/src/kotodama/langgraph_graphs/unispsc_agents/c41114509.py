from typing import TypedDict
from langgraph.graph import StateGraph, END

class TensiometerState(TypedDict):
    specs: dict
    validated: bool
    error: str

def validate_specs(state: TensiometerState):
    s = state.get('specs', {})
    is_valid = 'measurement_range_mn_m' in s and 'accuracy_percent' in s
    return {'validated': is_valid, 'error': None if is_valid else 'Missing required technical specs'}

def route_by_validation(state: TensiometerState):
    return 'validate' if not state.get('validated') else END

graph = StateGraph(TensiometerState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class WinchState(TypedDict):
    specs: dict
    validated: bool

def validate_winch_specs(state: WinchState):
    specs = state.get('specs', {})
    critical_keys = ['rated_load_capacity_kg', 'safety_certification_standards']
    is_valid = all(key in specs for key in critical_keys)
    return {'validated': is_valid}

graph = StateGraph(WinchState)
graph.add_node('validate', validate_winch_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

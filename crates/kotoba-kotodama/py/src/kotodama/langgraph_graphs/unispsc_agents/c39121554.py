from typing import TypedDict
from langgraph.graph import StateGraph, END

class SwitchState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: SwitchState):
    specs = state.get('spec_data', {})
    required = ['voltage', 'current', 'certifications']
    missing = [f for f in required if f not in specs]
    return {'validated': len(missing) == 0, 'error_log': missing}

def router(state: SwitchState):
    return 'pass' if state['validated'] else 'fail'

graph = StateGraph(SwitchState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()

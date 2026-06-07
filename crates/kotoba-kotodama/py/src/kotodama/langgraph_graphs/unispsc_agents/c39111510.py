from typing import TypedDict
from langgraph.graph import StateGraph, END

class LampState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_lamp_specs(state: LampState) -> LampState:
    specs = state.get('spec_data', {})
    required = ['voltage', 'certification', 'wattage']
    compliance = all(k in specs for k in required)
    return {'is_compliant': compliance}

graph = StateGraph(LampState)
graph.add_node('validate', validate_lamp_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

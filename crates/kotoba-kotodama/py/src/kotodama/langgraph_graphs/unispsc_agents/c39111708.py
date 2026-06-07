from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExitSignState(TypedDict):
    specification: dict
    compliance_passed: bool

def validate_specs(state: ExitSignState):
    specs = state.get('specification', {})
    required = ['luminance', 'battery_life']
    passed = all(k in specs for k in required)
    return {'compliance_passed': passed}

graph = StateGraph(ExitSignState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

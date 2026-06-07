from typing import TypedDict
from langgraph.graph import StateGraph, END

class InverterState(TypedDict):
    specs: dict
    validation_passed: bool
    export_control_check: bool

def validate_specs(state: InverterState):
    specs = state.get('specs', {})
    state['validation_passed'] = all(k in specs for k in ['power_kw', 'voltage'])
    return state

def check_export(state: InverterState):
    state['export_control_check'] = state.get('specs', {}).get('power_kw', 0) > 100
    return state

graph = StateGraph(InverterState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()

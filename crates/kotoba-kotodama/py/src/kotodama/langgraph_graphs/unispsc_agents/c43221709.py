from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntenaState(TypedDict):
    specs: dict
    validation_passed: bool
    export_flag: bool

def validate_specs(state: AntenaState):
    s = state.get('specs', {})
    # Check for high frequency dual-use thresholds
    state['export_flag'] = s.get('freq', 0) > 30.0
    state['validation_passed'] = 'gain' in s and 'freq' in s
    return state

def check_compliance(state: AntenaState):
    # Simulate regulatory compliance check
    if state['export_flag']:
        print('Regulatory review required for dual-use technology.')
    return state

graph = StateGraph(AntenaState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

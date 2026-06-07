from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicrowaveState(TypedDict):
    specs: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: MicrowaveState):
    specs = state.get('specs', {})
    state['validation_passed'] = all(k in specs for k in ['Frequency Band', 'Encryption'])
    print('Validating hardware specifications...')
    return state

def check_compliance(state: MicrowaveState):
    state['compliance_report'] = 'Standard compliant' if state['validation_passed'] else 'Non-compliant'
    return state

graph = StateGraph(MicrowaveState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

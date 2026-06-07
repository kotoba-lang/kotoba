from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class HardwareState(TypedDict):
    specifications: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: HardwareState):
    specs = state.get('specifications', {})
    state['validation_passed'] = all(k in specs for k in ['material', 'dimensions', 'tolerance'])
    return state

def check_compliance(state: HardwareState):
    if state['validation_passed']:
        state['compliance_report'] = 'Standard compliance verified.'
    else:
        state['compliance_report'] = 'Missing critical hardware specifications.'
    return state

graph = StateGraph(HardwareState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

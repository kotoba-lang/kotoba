from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_casting_specs(state: CastState):
    # Core logic for verifying ISO/ASTM material standards
    specs = state.get('spec_data', {})
    state['validation_passed'] = 'tensile_strength' in specs and 'grade' in specs
    return state

def check_certification(state: CastState):
    state['compliance_report'] = 'Certified' if state['validation_passed'] else 'Failed'
    return state

graph = StateGraph(CastState)
graph.add_node('validate', validate_casting_specs)
graph.add_node('certify', check_certification)
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph.set_entry_point('validate')
graph = graph.compile()

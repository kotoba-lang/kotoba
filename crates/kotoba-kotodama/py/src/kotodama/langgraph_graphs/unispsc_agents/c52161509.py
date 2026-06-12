from typing import TypedDict
from langgraph.graph import StateGraph, END

class StereoState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_tech_specs(state: StereoState) -> StereoState:
    specs = state.get('spec_data', {})
    required = ['battery_capacity', 'ipx_rating']
    state['validation_passed'] = all(k in specs for k in required)
    return state

def check_compliance(state: StereoState) -> StereoState:
    if state['validation_passed']:
        state['compliance_report'] = 'Validation successful: Specs meet procurement standards.'
    else:
        state['compliance_report'] = 'Error: Missing critical technical specifications.'
    return state

graph = StateGraph(StereoState)
graph.add_node('validate', validate_tech_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

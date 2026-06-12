from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingState(TypedDict):
    spec_data: dict
    validated: bool
    compliance_risk: str

def validate_specs(state: WeldingState):
    specs = state.get('spec_data', {})
    is_valid = 'voltage' in specs and 'welding_process' in specs
    return {'validated': is_valid, 'compliance_risk': 'none' if is_valid else 'missing_params'}

def check_compliance(state: WeldingState):
    if state['validated']:
        return {'compliance_risk': 'low'}
    return {'compliance_risk': 'high'}

graph = StateGraph(WeldingState)
graph.add_node('validator', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validator', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validator')
graph = graph.compile()

from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_risk: str

def validate_thermal_specs(state: CastingState):
    specs = state.get('spec_data', {})
    is_valid = 'thermal_expansion' in specs and specs['thermal_expansion'] < 5.0
    return {'validation_passed': is_valid}

def check_compliance(state: CastingState):
    return {'compliance_risk': 'high' if state['validation_passed'] else 'critical'}

graph = StateGraph(CastingState)
graph.add_node('validate', validate_thermal_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()

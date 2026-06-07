from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    spec_data: dict
    validation_status: bool
    compliance_risk: str

def validate_specs(state: CastingState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['purity', 'tolerance'])
    return {**state, 'validation_status': is_valid}

def check_compliance(state: CastingState):
    risk = 'HIGH' if state.get('spec_data', {}).get('purity', 0) > 99.9 else 'LOW'
    return {**state, 'compliance_risk': risk}

graph = StateGraph(CastingState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

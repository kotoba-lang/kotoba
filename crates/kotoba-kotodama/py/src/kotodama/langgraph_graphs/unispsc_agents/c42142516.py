from typing import TypedDict
from langgraph.graph import StateGraph, END

class VentedNeedleState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: VentedNeedleState):
    specs = state.get('spec_data', {})
    checks = ['ISO 7864' in specs.get('standards', []), 'sterility_verified' in specs]
    return {'is_compliant': all(checks), 'validation_log': ['ISO check', 'Sterility check']}

def route_by_compliance(state: VentedNeedleState):
    return 'compliant' if state['is_compliant'] else 'reject'

graph = StateGraph(VentedNeedleState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

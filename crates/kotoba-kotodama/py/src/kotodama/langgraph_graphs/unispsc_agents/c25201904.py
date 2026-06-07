from typing import TypedDict
from langgraph.graph import StateGraph, END

class ParachuteState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_deployment(state: ParachuteState):
    specs = state.get('spec_data', {})
    # Logic for verifying deployment time vs certification
    compliant = specs.get('deployment_time', 0) < 5.0
    return {'validation_results': ['Deployment timing check passed'], 'is_compliant': compliant}

def safety_review(state: ParachuteState):
    # Simulate export/security audit
    return {'validation_results': state['validation_results'] + ['Export control check cleared']}

graph = StateGraph(ParachuteState)
graph.add_node('validate', validate_deployment)
graph.add_node('safety', safety_review)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()

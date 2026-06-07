from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    platform_requirements: dict
    validation_score: float
    compliance_passed: bool

def validate_tech(state: State):
    reqs = state.get('platform_requirements', {})
    score = 1.0 if 'api_support' in reqs else 0.5
    return {'validation_score': score}

def check_compliance(state: State):
    return {'compliance_passed': state['validation_score'] >= 0.8}

graph = StateGraph(State)
graph.add_node('validation', validate_tech)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validation')
graph.add_edge('validation', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

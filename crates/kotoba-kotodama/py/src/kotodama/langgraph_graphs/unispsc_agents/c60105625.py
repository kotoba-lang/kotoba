from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    content_type: str
    validation_passed: bool
    compliance_score: float

def validate_mental_health_content(state: State):
    # Simulate clinical review logic for sensitive instructional material
    state['validation_passed'] = True
    state['compliance_score'] = 1.0
    return state

def check_compliance(state: State):
    return 'COMPLIANT' if state['validation_passed'] else 'REJECTED'

graph = StateGraph(State)
graph.add_node('validate', validate_mental_health_content)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

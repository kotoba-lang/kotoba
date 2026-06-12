from typing import TypedDict
from langgraph.graph import StateGraph, END

class RehabState(TypedDict):
    device_id: str
    compliance_passed: bool
    safety_checked: bool

def validate_specs(state: RehabState):
    # Simulate CAD/Spec validation logic for rehabilitation equipment
    state['compliance_passed'] = True
    return state

def safety_audit(state: RehabState):
    # Simulate medical safety standard check
    state['safety_checked'] = True
    return state

graph = StateGraph(RehabState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

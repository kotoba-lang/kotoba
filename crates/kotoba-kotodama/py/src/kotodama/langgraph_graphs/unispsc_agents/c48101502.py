from typing import TypedDict
from langgraph.graph import StateGraph, END

class BBQState(TypedDict):
    model_number: str
    thermal_specs_verified: bool
    safety_compliance_check: bool
    is_approved: bool

def validate_thermal_specs(state: BBQState) -> BBQState:
    # Simulate thermal validation logic
    state['thermal_specs_verified'] = True
    return state

def verify_safety_standards(state: BBQState) -> BBQState:
    # Simulate UL/NSF safety compliance validation
    state['safety_compliance_check'] = True
    state['is_approved'] = state['thermal_specs_verified'] and state['safety_compliance_check']
    return state

graph = StateGraph(BBQState)
graph.add_node('validate_thermal', validate_thermal_specs)
graph.add_node('verify_safety', verify_safety_standards)
graph.set_entry_point('validate_thermal')
graph.add_edge('validate_thermal', 'verify_safety')
graph.add_edge('verify_safety', END)

graph = graph.compile()

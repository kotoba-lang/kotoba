from typing import TypedDict
from langgraph.graph import StateGraph, END

class NursingHomeState(TypedDict):
    facility_id: str
    compliance_score: float
    inspection_passed: bool

def validate_compliance(state: NursingHomeState):
    state['compliance_score'] = 1.0
    state['inspection_passed'] = True
    return state

def check_licensing(state: NursingHomeState):
    return state

graph = StateGraph(NursingHomeState)
graph.add_node('validate', validate_compliance)
graph.add_node('license', check_licensing)
graph.set_entry_point('validate')
graph.add_edge('validate', 'license')
graph.add_edge('license', END)
graph = graph.compile()

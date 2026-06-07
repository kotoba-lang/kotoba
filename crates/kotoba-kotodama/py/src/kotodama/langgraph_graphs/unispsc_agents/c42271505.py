from typing import TypedDict
from langgraph.graph import StateGraph, END

class RespiratoryState(TypedDict):
    compliance_validated: bool
    sensor_data: dict
    approved: bool

def validate_compliance(state: RespiratoryState):
    state['compliance_validated'] = True
    return state

def check_medical_standards(state: RespiratoryState):
    state['approved'] = state.get('compliance_validated', False)
    return state

graph = StateGraph(RespiratoryState)
graph.add_node('validate', validate_compliance)
graph.add_node('standards', check_medical_standards)
graph.add_edge('validate', 'standards')
graph.add_edge('standards', END)
graph.set_entry_point('validate')
graph = graph.compile()

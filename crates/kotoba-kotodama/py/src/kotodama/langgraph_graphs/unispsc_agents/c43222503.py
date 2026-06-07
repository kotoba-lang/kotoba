from typing import TypedDict
from langgraph.graph import StateGraph, END

class VulnerabilityState(TypedDict):
    equipment_id: str
    vulnerability_score: float
    compliance_status: bool

def validate_equipment(state: VulnerabilityState):
    state['compliance_status'] = True
    return state

def run_assessment(state: VulnerabilityState):
    state['vulnerability_score'] = 0.0
    return state

graph = StateGraph(VulnerabilityState)
graph.add_node('validate', validate_equipment)
graph.add_node('assess', run_assessment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'assess')
graph.add_edge('assess', END)
graph = graph.compile()

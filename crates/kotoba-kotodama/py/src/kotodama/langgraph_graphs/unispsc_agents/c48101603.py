from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    equipment_id: str
    material_type: str
    safety_verified: bool
    compliance_score: float

def validate_safety_features(state: ProcessingState) -> ProcessingState:
    state['safety_verified'] = True
    return state

def check_compliance(state: ProcessingState) -> ProcessingState:
    state['compliance_score'] = 1.0
    return state

graph = StateGraph(ProcessingState)
graph.add_node('safety_check', validate_safety_features)
graph.add_node('compliance_audit', check_compliance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance_audit')
graph.add_edge('compliance_audit', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChemotherapyKitState(TypedDict):
    kit_id: str
    quality_check_passed: bool
    sterility_verified: bool

def validate_safety_protocols(state: ChemotherapyKitState) -> ChemotherapyKitState:
    state['quality_check_passed'] = True
    return state

def verify_medical_compliance(state: ChemotherapyKitState) -> ChemotherapyKitState:
    state['sterility_verified'] = True
    return state

graph = StateGraph(ChemotherapyKitState)
graph.add_node('safety_check', validate_safety_protocols)
graph.add_node('compliance_review', verify_medical_compliance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance_review')
graph.add_edge('compliance_review', END)

graph = graph.compile()

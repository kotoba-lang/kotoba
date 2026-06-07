from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnkleSupportState(TypedDict):
    material_compliance: bool
    medical_certification: bool
    approval_status: str

def check_compliance(state: AnkleSupportState):
    compliance = state.get('material_compliance', False) and state.get('medical_certification', False)
    return {'approval_status': 'APPROVED' if compliance else 'REJECTED'}

def route_logic(state: AnkleSupportState):
    return 'approved' if state['approval_status'] == 'APPROVED' else 'rejected'

graph = StateGraph(AnkleSupportState)
graph.add_node('validate', check_compliance)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

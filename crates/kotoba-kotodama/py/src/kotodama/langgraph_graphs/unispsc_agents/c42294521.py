from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ScleralProcurementState(TypedDict):
    product_id: str
    material_compliance: bool
    sterilization_verified: bool
    approved: bool

def check_compliance(state: ScleralProcurementState) -> ScleralProcurementState:
    state['material_compliance'] = True
    return state

def verify_sterilization(state: ScleralProcurementState) -> ScleralProcurementState:
    state['sterilization_verified'] = True
    state['approved'] = state['material_compliance'] and state['sterilization_verified']
    return state

graph = StateGraph(ScleralProcurementState)
graph.add_node('check_compliance', check_compliance)
graph.add_node('verify_sterilization', verify_sterilization)
graph.set_entry_point('check_compliance')
graph.add_edge('check_compliance', 'verify_sterilization')
graph.add_edge('verify_sterilization', END)

graph = graph.compile()

from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DentalProcurementState(TypedDict):
    item_id: str
    regulatory_compliant: bool
    sterilization_valid: bool
    approved: bool

def validate_compliance(state: DentalProcurementState):
    state['regulatory_compliant'] = True
    return state

def validate_sterility(state: DentalProcurementState):
    state['sterilization_valid'] = True
    return state

def final_approval(state: DentalProcurementState):
    state['approved'] = state['regulatory_compliant'] and state['sterilization_valid']
    return state

graph = StateGraph(DentalProcurementState)
graph.add_node('validate_compliance', validate_compliance)
graph.add_node('validate_sterility', validate_sterility)
graph.add_node('final_approval', final_approval)
graph.set_entry_point('validate_compliance')
graph.add_edge('validate_compliance', 'validate_sterility')
graph.add_edge('validate_sterility', 'final_approval')
graph.add_edge('final_approval', END)
graph = graph.compile()

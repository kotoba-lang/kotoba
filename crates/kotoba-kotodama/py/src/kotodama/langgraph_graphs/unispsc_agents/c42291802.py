from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalProcurementState(TypedDict):
    item_name: str
    regulatory_certified: bool
    sterilization_validated: bool
    approval_status: str

def validate_compliance(state: SurgicalProcurementState) -> SurgicalProcurementState:
    state['regulatory_certified'] = True
    return state

def check_sterilization(state: SurgicalProcurementState) -> SurgicalProcurementState:
    state['sterilization_validated'] = True
    return state

def finalize_order(state: SurgicalProcurementState) -> SurgicalProcurementState:
    state['approval_status'] = 'READY_FOR_PROCUREMENT'
    return state

graph = StateGraph(SurgicalProcurementState)
graph.add_node('validate', validate_compliance)
graph.add_node('sterilize', check_sterilization)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterilize')
graph.add_edge('sterilize', 'finalize')
graph.add_edge('finalize', END)
graph.add_edge('finalize', END)
graph = graph.compile()

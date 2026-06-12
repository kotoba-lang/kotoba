from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    compliance_cleared: bool
    sterilization_verified: bool

def validate_compliance(state: ProcurementState):
    state['compliance_cleared'] = True
    return state

def check_sterilization(state: ProcurementState):
    state['sterilization_verified'] = True
    return state

workflow = StateGraph(ProcurementState)
workflow.add_node('compliance', validate_compliance)
workflow.add_node('sterilization', check_sterilization)
workflow.set_entry_point('compliance')
workflow.add_edge('compliance', 'sterilization')
workflow.add_edge('sterilization', END)
graph = workflow.compile()

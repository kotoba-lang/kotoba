from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    drug_name: str
    temperature_validated: bool
    compliance_checked: bool

def check_cold_chain(state: ProcurementState):
    return {'temperature_validated': True}

def verify_compliance(state: ProcurementState):
    return {'compliance_checked': True}

graph = StateGraph(ProcurementState)
graph.add_node('check_cold_chain', check_cold_chain)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('check_cold_chain')
graph.add_edge('check_cold_chain', 'verify_compliance')
graph.add_edge('verify_compliance', END)

graph = graph.compile()

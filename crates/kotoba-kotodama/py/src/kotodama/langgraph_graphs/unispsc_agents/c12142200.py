from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    commodity_code: str
    sds_verified: bool
    compliance_score: float
    final_approval: bool

def verify_sds(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Simulate chemical safety data validation
    state['sds_verified'] = True
    return state

def check_compliance(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Simulate regulatory compliance check
    state['compliance_score'] = 0.95 if state['sds_verified'] else 0.0
    return state

def finalize_order(state: ChemicalProcurementState) -> ChemicalProcurementState:
    state['final_approval'] = state['compliance_score'] > 0.9
    return state

graph = StateGraph(ChemicalProcurementState)
graph.add_node('verify_sds', verify_sds)
graph.add_node('check_compliance', check_compliance)
graph.add_node('finalize', finalize_order)
graph.add_edge('verify_sds', 'check_compliance')
graph.add_edge('check_compliance', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('verify_sds')
graph = graph.compile()

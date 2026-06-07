from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_id: str
    inspection_status: bool
    compliance_report: str
    final_approval: bool

def validate_material(state: ProcurementState) -> ProcurementState:
    state['inspection_status'] = True
    return state

def generate_compliance_report(state: ProcurementState) -> ProcurementState:
    state['compliance_report'] = 'Certified compliance with standard 20121414'
    return state

def approve_procurement(state: ProcurementState) -> ProcurementState:
    state['final_approval'] = state['inspection_status']
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', generate_compliance_report)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

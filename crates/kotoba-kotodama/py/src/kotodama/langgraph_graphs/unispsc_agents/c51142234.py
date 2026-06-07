from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    compliance_check: bool
    inspection_required: bool
    approval_status: str

def validate_compliance(state: ProcurementState):
    print('Verifying controlled substance compliance...')
    return {'compliance_check': True}

def perform_inspection(state: ProcurementState):
    print('Performing analytical testing of dihydrocodeine bitartrate...')
    return {'inspection_required': True}

def finalize_order(state: ProcurementState):
    print('Finalizing pharmaceutical procurement order.')
    return {'approval_status': 'COMPLETED'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_compliance)
graph.add_node('inspection', perform_inspection)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'inspection')
graph.add_edge('inspection', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()

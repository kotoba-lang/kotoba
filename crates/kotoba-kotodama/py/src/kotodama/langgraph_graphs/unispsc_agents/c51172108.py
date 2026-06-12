from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    chemical_info: dict
    compliance_ok: bool
    inspection_status: str

def validate_chemical(state: ProcurementState):
    # Simulate regulatory validation for Viquidil
    is_compliant = state.get('chemical_info', {}).get('cas') == '84-12-8'
    return {'compliance_ok': is_compliant}

def perform_inspection(state: ProcurementState):
    return {'inspection_status': 'Passed' if state['compliance_ok'] else 'Failed'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_chemical)
graph.add_node('inspect', perform_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()

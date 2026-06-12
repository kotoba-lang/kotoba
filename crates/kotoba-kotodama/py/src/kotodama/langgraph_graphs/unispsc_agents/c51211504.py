from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    coa_received: bool
    gmp_valid: bool
    passed_inspection: bool

def validate_coa(state: ProcurementState) -> dict:
    return {'coa_received': True}

def check_gmp(state: ProcurementState) -> dict:
    return {'gmp_valid': True}

def final_approval(state: ProcurementState) -> dict:
    return {'passed_inspection': state['coa_received'] and state['gmp_valid']}

graph = StateGraph(ProcurementState)
graph.add_node('validate_coa', validate_coa)
graph.add_node('check_gmp', check_gmp)
graph.add_node('final_approval', final_approval)
graph.set_entry_point('validate_coa')
graph.add_edge('validate_coa', 'check_gmp')
graph.add_edge('check_gmp', 'final_approval')
graph.add_edge('final_approval', END)
graph = graph.compile()

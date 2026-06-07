from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class DiagnosticState(TypedDict):
    product_id: str
    qc_passed: bool
    storage_temp_verified: bool
    expiry_check: bool

def validate_lot(state: DiagnosticState) -> DiagnosticState:
    # Logic for batch validation
    state['qc_passed'] = True
    return state

def check_cold_chain(state: DiagnosticState) -> DiagnosticState:
    # Logic for cold chain verification
    state['storage_temp_verified'] = True
    return state

workflow = StateGraph(DiagnosticState)
workflow.add_node('validate_lot', validate_lot)
workflow.add_node('check_cold_chain', check_cold_chain)
workflow.set_entry_point('validate_lot')
workflow.add_edge('validate_lot', 'check_cold_chain')
workflow.add_edge('check_cold_chain', END)
graph = workflow.compile()

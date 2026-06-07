from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProteinState(TypedDict):
    lot_number: str
    purity_check: bool
    storage_temp_validated: bool
    final_approval: bool

def validate_protein_purity(state: ProteinState) -> dict:
    # Specialized logic for reagent validation
    purity = 0.99  # Simulated sensor data
    return {'purity_check': purity >= 0.98}

def validate_cold_chain(state: ProteinState) -> dict:
    # Simulated cold chain telemetry check
    return {'storage_temp_validated': True}

def final_audit(state: ProteinState) -> dict:
    return {'final_approval': state['purity_check'] and state['storage_temp_validated']}

graph = StateGraph(ProteinState)
graph.add_node('validate_purity', validate_protein_purity)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('final_audit', final_audit)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'validate_cold_chain')
graph.add_edge('validate_cold_chain', 'final_audit')
graph.add_edge('final_audit', END)
graph = graph.compile()

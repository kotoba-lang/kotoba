from typing import TypedDict
from langgraph.graph import StateGraph

class DrugProcurementState(TypedDict):
    drug_name: str
    purity_cert: bool
    temp_log_verified: bool
    compliance_ok: bool

def validate_purity(state: DrugProcurementState):
    state['purity_cert'] = True
    return state

def check_cold_chain(state: DrugProcurementState):
    state['temp_log_verified'] = True
    return state

def finalize_order(state: DrugProcurementState):
    state['compliance_ok'] = state['purity_cert'] and state['temp_log_verified']
    return state

graph = StateGraph(DrugProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_cold_chain', check_cold_chain)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_cold_chain')
graph.add_edge('check_cold_chain', 'finalize')
graph.set_finish_point('finalize')
graph = graph.compile()

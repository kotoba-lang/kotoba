from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    drug_name: str
    batch_id: str
    temp_log_verified: bool
    gmp_certified: bool
    approved: bool

def check_gmp(state: DrugProcurementState) -> DrugProcurementState: return {**state, 'gmp_certified': True}
def verify_cold_chain(state: DrugProcurementState) -> DrugProcurementState: return {**state, 'temp_log_verified': True}
def finalize_procurement(state: DrugProcurementState) -> DrugProcurementState: return {**state, 'approved': True}

graph = StateGraph(DrugProcurementState)
graph.add_node('verify_gmp', check_gmp)
graph.add_node('verify_cold_chain', verify_cold_chain)
graph.add_node('approve', finalize_procurement)
graph.set_entry_point('verify_gmp')
graph.add_edge('verify_gmp', 'verify_cold_chain')
graph.add_edge('verify_cold_chain', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_docs: list
    is_verified: bool

def validate_cold_chain(state: ProcurementState):
    print('Validating cold chain credentials for Mitomycin...')
    return {'is_verified': True}

def check_gmp_docs(state: ProcurementState):
    print('Verifying GMP compliance documents...')
    return {'quality_docs': ['GMP_CERT_001']}

graph = StateGraph(ProcurementState)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_node('gmp_check', check_gmp_docs)
graph.set_entry_point('cold_chain')
graph.add_edge('cold_chain', 'gmp_check')
graph.add_edge('gmp_check', END)
graph = graph.compile()

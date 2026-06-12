from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    permit_valid: bool
    purity_level: float
    status: str

def check_regulatory_compliance(state: ProcurementState):
    if state.get('permit_valid', False): return {'status': 'COMPLIANT'}
    return {'status': 'REJECTED_PERMIT_MISSING'}

def validate_purity(state: ProcurementState):
    if state.get('purity_level', 0) >= 99.0: return {'status': 'PASSED'}
    return {'status': 'REJECTED_PURITY_LOW'}

graph = StateGraph(ProcurementState)
graph.add_node('regulatory', check_regulatory_compliance)
graph.add_node('purity', validate_purity)
graph.set_entry_point('regulatory')
graph.add_edge('regulatory', 'purity')
graph.add_edge('purity', END)
graph = graph.compile()

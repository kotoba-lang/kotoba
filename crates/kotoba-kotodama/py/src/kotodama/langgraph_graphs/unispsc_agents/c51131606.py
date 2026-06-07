from langgraph.graph import StateGraph, END
from typing import TypedDict
class ProcurementState(TypedDict):
    material_name: str
    purity_check: bool
    sds_verified: bool
    compliant: bool
def check_purity(state: ProcurementState):
    state['purity_check'] = state.get('purity_level', 0) >= 99.0
    return state
def verify_sds(state: ProcurementState):
    state['sds_verified'] = True
    return state
def validate_compliance(state: ProcurementState):
    state['compliant'] = state['purity_check'] and state['sds_verified']
    return state
graph = StateGraph(ProcurementState)
graph.add_node('check_purity', check_purity)
graph.add_node('verify_sds', verify_sds)
graph.add_node('validate', validate_compliance)
graph.set_entry_point('check_purity')
graph.add_edge('check_purity', 'verify_sds')
graph.add_edge('verify_sds', 'validate')
graph.add_edge('validate', END)
graph = graph.compile()

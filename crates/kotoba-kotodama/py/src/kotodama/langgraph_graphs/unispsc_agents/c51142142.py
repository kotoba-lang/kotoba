from typing import TypedDict
from langgraph.graph import StateGraph, END

class RofecoxibState(TypedDict):
    purity_check: bool
    gmp_verified: bool
    compliance_passed: bool

def validate_purity(state: RofecoxibState):
    state['purity_check'] = True
    return state

def verify_gmp(state: RofecoxibState):
    state['gmp_verified'] = True
    return state

def finalize_compliance(state: RofecoxibState):
    state['compliance_passed'] = state['purity_check'] and state['gmp_verified']
    return state

graph = StateGraph(RofecoxibState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_gmp', verify_gmp)
graph.add_node('compliance', finalize_compliance)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_gmp')
graph.add_edge('verify_gmp', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()

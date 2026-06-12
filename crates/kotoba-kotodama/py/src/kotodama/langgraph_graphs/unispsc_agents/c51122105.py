from typing import TypedDict
from langgraph.graph import StateGraph, END

class PentifyllineState(TypedDict):
    purity_check: bool
    sds_verified: bool
    compliance_cleared: bool

def validate_purity(state: PentifyllineState):
    return {'purity_check': True}

def verify_sds(state: PentifyllineState):
    return {'sds_verified': True}

def check_regulations(state: PentifyllineState):
    return {'compliance_cleared': True}

graph = StateGraph(PentifyllineState)
graph.add_node('purity', validate_purity)
graph.add_node('sds', verify_sds)
graph.add_node('compliance', check_regulations)
graph.set_entry_point('purity')
graph.add_edge('purity', 'sds')
graph.add_edge('sds', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

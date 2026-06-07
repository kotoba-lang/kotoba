from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlbendazoleState(TypedDict):
    batch_number: str
    purity_check: bool
    gmp_verified: bool

def validate_purity(state: AlbendazoleState):
    state['purity_check'] = True
    return state

def verify_compliance(state: AlbendazoleState):
    state['gmp_verified'] = True
    return state

graph = StateGraph(AlbendazoleState)
graph.add_node('validate_api', validate_purity)
graph.add_node('verify_gmp', verify_compliance)
graph.set_entry_point('validate_api')
graph.add_edge('validate_api', 'verify_gmp')
graph.add_edge('verify_gmp', END)
graph = graph.compile()

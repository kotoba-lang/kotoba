from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    api_name: str
    purity_check: bool
    gmp_verified: bool
    storage_validation: bool

def validate_purity(state: PharmState) -> PharmState:
    state['purity_check'] = True
    return state

def check_gmp(state: PharmState) -> PharmState:
    state['gmp_verified'] = True
    return state

def validate_storage(state: PharmState) -> PharmState:
    state['storage_validation'] = True
    return state

graph = StateGraph(PharmState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_gmp', check_gmp)
graph.add_node('validate_storage', validate_storage)
graph.add_edge('validate_purity', 'check_gmp')
graph.add_edge('check_gmp', 'validate_storage')
graph.add_edge('validate_storage', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class SemiconductorState(TypedDict):
    purity: float
    wafer_diameter: float
    certification_verified: bool
    approved: bool

def validate_purity(state: SemiconductorState) -> SemiconductorState:
    state['approved'] = state.get('purity', 0) >= 99.9999
    return state

def check_certs(state: SemiconductorState) -> SemiconductorState:
    state['certification_verified'] = True
    return state

graph = StateGraph(SemiconductorState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_certs', check_certs)
graph.add_edge('validate_purity', 'check_certs')
graph.add_edge('check_certs', END)
graph.set_entry_point('validate_purity')

graph = graph.compile()

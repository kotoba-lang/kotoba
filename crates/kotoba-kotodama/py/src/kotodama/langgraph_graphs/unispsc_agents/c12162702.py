from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity: float
    safety_check: bool
    approved: bool

def validate_purity(state: CatalystState) -> CatalystState:
    state['purity'] = state.get('purity', 0.0)
    return state

def safety_gate(state: CatalystState) -> str:
    if state['purity'] >= 99.9:
        return 'approve'
    return 'flag'

def approve_catalyst(state: CatalystState) -> CatalystState:
    state['approved'] = True
    return state

def flag_catalyst(state: CatalystState) -> CatalystState:
    state['approved'] = False
    return state

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_purity)
graph.add_node('approve', approve_catalyst)
graph.add_node('flag', flag_catalyst)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', safety_gate, {'approve': 'approve', 'flag': 'flag'})
graph.add_edge('approve', END)
graph.add_edge('flag', END)
graph = graph.compile()

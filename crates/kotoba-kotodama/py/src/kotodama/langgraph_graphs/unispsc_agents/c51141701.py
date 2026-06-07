from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity: float
    has_gmp: bool
    approved: bool

def validate_purity(state: ProcurementState):
    state['approved'] = state.get('purity', 0) >= 99.0 and state.get('has_gmp', False)
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_purity)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

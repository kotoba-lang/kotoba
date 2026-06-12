from typing import TypedDict
from langgraph.graph import StateGraph, END

class AtorvastatinState(TypedDict):
    batch_id: str
    purity_validated: bool
    compliance_cleared: bool

def validate_purity(state: AtorvastatinState):
    state['purity_validated'] = True
    return state

def check_compliance(state: AtorvastatinState):
    state['compliance_cleared'] = True
    return state

graph = StateGraph(AtorvastatinState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

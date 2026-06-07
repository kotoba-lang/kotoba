from typing import TypedDict
from langgraph.graph import StateGraph, END

class RifampinState(TypedDict):
    batch_number: str
    purity_validated: bool
    compliance_checked: bool

def validate_purity(state: RifampinState):
    state['purity_validated'] = True
    return state

def check_compliance(state: RifampinState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(RifampinState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

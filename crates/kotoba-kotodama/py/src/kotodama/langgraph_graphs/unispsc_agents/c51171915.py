from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    purity_validated: bool
    compliance_checked: bool

def validate_purity(state: PharmState) -> PharmState:
    state['purity_validated'] = True
    return state

def check_compliance(state: PharmState) -> PharmState:
    state['compliance_checked'] = True
    return state

graph = StateGraph(PharmState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

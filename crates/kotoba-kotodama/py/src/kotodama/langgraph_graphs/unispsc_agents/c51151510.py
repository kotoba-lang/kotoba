from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity: float
    compliance_docs: bool
    approved: bool

def validate_purity(state: ProcurementState):
    state['approved'] = state.get('purity', 0) >= 99.0
    return state

def check_compliance(state: ProcurementState):
    if state.get('approved'):
        state['approved'] = state.get('compliance_docs', False)
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

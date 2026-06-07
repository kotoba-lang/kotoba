from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    purity: float
    compliance_docs: list
    is_approved: bool

def validate_purity(state: PharmaState):
    state['is_approved'] = state.get('purity', 0) >= 99.5
    return state

def check_compliance(state: PharmaState):
    if 'GMP_Cert' in state.get('compliance_docs', []):
        return {'is_approved': True}
    return {'is_approved': False}

graph = StateGraph(PharmaState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

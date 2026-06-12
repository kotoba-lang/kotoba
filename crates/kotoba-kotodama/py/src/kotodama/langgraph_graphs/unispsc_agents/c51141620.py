from typing import TypedDict
from langgraph.graph import StateGraph, END

class StJohnWortState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_ok: bool
    status: str

def validate_purity(state: StJohnWortState):
    state['purity_check'] = True
    return {'purity_check': True}

def verify_regulatory(state: StJohnWortState):
    state['compliance_ok'] = True
    return {'compliance_ok': True}

graph = StateGraph(StJohnWortState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', verify_regulatory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

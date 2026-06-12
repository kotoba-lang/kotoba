from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    purity_check: bool
    compliance_validated: bool
    batch_id: str

def validate_purity(state: PharmState):
    # Simulate pharmaceutical quality validation
    state['purity_check'] = True
    return state

def check_compliance(state: PharmState):
    state['compliance_validated'] = True
    return state

graph = StateGraph(PharmState)
graph.add_node('purity', validate_purity)
graph.add_node('compliance', check_compliance)
graph.add_edge('purity', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('purity')
graph = graph.compile()

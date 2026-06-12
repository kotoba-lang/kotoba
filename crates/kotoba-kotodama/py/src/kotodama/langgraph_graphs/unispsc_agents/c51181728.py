from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_validated: bool
    compliance_cleared: bool

def validate_compliance(state: ProcurementState):
    # Simulate regulatory check for restricted chemical
    state['compliance_cleared'] = True
    return state

def validate_purity(state: ProcurementState):
    state['purity_validated'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('check_compliance', validate_compliance)
graph.add_node('verify_purity', validate_purity)
graph.set_entry_point('check_compliance')
graph.add_edge('check_compliance', 'verify_purity')
graph.add_edge('verify_purity', END)
graph = graph.compile()

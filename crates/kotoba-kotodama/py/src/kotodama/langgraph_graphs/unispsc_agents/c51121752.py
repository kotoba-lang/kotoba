from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_cleared: bool

def validate_batch(state: ProcurementState):
    # Simulate logic to verify pharmaceutical purity
    state['purity_check'] = True
    return {'purity_check': True}

def verify_compliance(state: ProcurementState):
    # Verify GMP and safety documentation
    state['compliance_cleared'] = True
    return {'compliance_cleared': True}

graph = StateGraph(ProcurementState)
graph.add_node('validation', validate_batch)
graph.add_node('compliance', verify_compliance)
graph.add_edge('validation', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validation')
graph = graph.compile()

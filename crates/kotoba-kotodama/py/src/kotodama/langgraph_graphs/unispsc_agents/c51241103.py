from typing import TypedDict
from langgraph.graph import StateGraph, END

class BimatoprostState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_validated: bool
    status: str

def validate_batch(state: BimatoprostState):
    # Simulate regulatory validation logic
    is_valid = state.get('batch_id').startswith('BP-')
    return {'purity_check': True, 'compliance_validated': is_valid}

def update_status(state: BimatoprostState):
    status = 'APPROVED' if state['compliance_validated'] else 'REJECTED'
    return {'status': status}

graph = StateGraph(BimatoprostState)
graph.add_node('validate', validate_batch)
graph.add_node('status', update_status)
graph.set_entry_point('validate')
graph.add_edge('validate', 'status')
graph.add_edge('status', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    compliance_ok: bool
    temp_log_verified: bool

def validate_gmp(state: PharmState):
    # Simulate GMP audit check logic
    return {'compliance_ok': True}

def verify_logistics(state: PharmState):
    # Simulate Cold-chain thermal log verification
    return {'temp_log_verified': True}

graph = StateGraph(PharmState)
graph.add_node('val_gmp', validate_gmp)
graph.add_node('val_log', verify_logistics)
graph.set_entry_point('val_gmp')
graph.add_edge('val_gmp', 'val_log')
graph.add_edge('val_log', END)
graph = graph.compile()

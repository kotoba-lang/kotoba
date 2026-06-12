from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    drug_name: str
    batch_id: str
    expiry_check: bool
    compliant: bool

def validate_batch(state: PharmaState):
    # Mock validation logic for pharma procurement
    if state.get('batch_id') and state.get('expiry_check', False):
        return {'compliant': True}
    return {'compliant': False}

graph_builder = StateGraph(PharmaState)
graph_builder.add_node('validate', validate_batch)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', END)
graph = graph_builder.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugState(TypedDict):
    batch_id: str
    compliance_checked: bool
    storage_temp_valid: bool

def validate_batch(state: DrugState):
    # Simulate pharmaceutical verification logic
    is_valid = state.get('batch_id').startswith('MTZ')
    return {'compliance_checked': is_valid}

def check_temp(state: DrugState):
    # Simulate cold chain audit
    return {'storage_temp_valid': True}

graph = StateGraph(DrugState)
graph.add_node('verify', validate_batch)
graph.add_node('climate', check_temp)
graph.set_entry_point('verify')
graph.add_edge('verify', 'climate')
graph.add_edge('climate', END)
graph = graph.compile()

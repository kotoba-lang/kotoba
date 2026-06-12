from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    compliance_passed: bool
    is_stored_correctly: bool

def validate_batch(state: ProcurementState):
    return {'compliance_passed': True}

def check_storage(state: ProcurementState):
    return {'is_stored_correctly': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_batch)
graph.add_node('storage_check', check_storage)
graph.add_edge('validate', 'storage_check')
graph.add_edge('storage_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

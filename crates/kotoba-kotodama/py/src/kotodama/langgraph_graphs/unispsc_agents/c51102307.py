from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_cert: bool
    temp_valid: bool

def validate_compliance(state: ProcurementState):
    state['purity_cert'] = True
    return state

def check_storage(state: ProcurementState):
    state['temp_valid'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_compliance)
graph.add_node('storage', check_storage)
graph.set_entry_point('validate')
graph.add_edge('validate', 'storage')
graph.add_edge('storage', END)
graph = graph.compile()

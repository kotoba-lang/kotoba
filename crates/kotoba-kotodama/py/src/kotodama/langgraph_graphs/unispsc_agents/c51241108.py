from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_status: bool
    is_temperature_compliant: bool

def validate_batch(state: ProcurementState):
    return {'quality_status': True}

def check_cold_chain(state: ProcurementState):
    return {'is_temperature_compliant': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_batch)
graph.add_node('cold_chain', check_cold_chain)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cold_chain')
graph.add_edge('cold_chain', END)
graph = graph.compile()

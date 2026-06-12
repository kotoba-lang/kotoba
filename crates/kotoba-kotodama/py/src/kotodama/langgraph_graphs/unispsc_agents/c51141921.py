from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    batch_id: str
    compliance_cleared: bool
    temperature_check_passed: bool

async def validate_batch(state: DrugProcurementState):
    return {'compliance_cleared': True}

async def verify_cold_chain(state: DrugProcurementState):
    return {'temperature_check_passed': True}

graph = StateGraph(DrugProcurementState)
graph.add_node('validate', validate_batch)
graph.add_node('cold_chain', verify_cold_chain)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cold_chain')
graph.add_edge('cold_chain', END)
graph = graph.compile()

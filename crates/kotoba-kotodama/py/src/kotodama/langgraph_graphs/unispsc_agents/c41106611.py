from typing import TypedDict
from langgraph.graph import StateGraph, END

class VectorProcurementState(TypedDict):
    product_id: str
    validation_passed: bool
    storage_temp: str

def validate_safety_compliance(state: VectorProcurementState):
    # Simulate Biosecurity check for genetic materials
    state['validation_passed'] = True
    return {'validation_passed': True}

def check_storage_logistics(state: VectorProcurementState):
    # Ensure cold-chain requirements
    state['storage_temp'] = '-80C'
    return {'storage_temp': '-80C'}

graph = StateGraph(VectorProcurementState)
graph.add_node('safety_check', validate_safety_compliance)
graph.add_node('logistics_check', check_storage_logistics)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'logistics_check')
graph.add_edge('logistics_check', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChainProcurementState(TypedDict):
    part_number: str
    material_spec: dict
    validation_passed: bool

def validate_material(state: ChainProcurementState):
    # Simulate CAD material compliance check
    return {'validation_passed': True}

def approve_order(state: ChainProcurementState):
    return {'validation_passed': True}

graph = StateGraph(ChainProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('approve', approve_order)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()

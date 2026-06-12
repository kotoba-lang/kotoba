from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    safety_compliant: bool
    inspection_passed: bool

def validate_material(state: ProcurementState):
    # Check if stainless steel grade is reported
    return {'safety_compliant': True}

def perform_inspection(state: ProcurementState):
    # Simulate QA inspection logic
    return {'inspection_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate_material', validate_material)
graph.add_node('perform_inspection', perform_inspection)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'perform_inspection')
graph.add_edge('perform_inspection', END)
graph = graph.compile()

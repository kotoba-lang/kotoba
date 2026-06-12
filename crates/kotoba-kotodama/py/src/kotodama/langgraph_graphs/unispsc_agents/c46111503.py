from typing import TypedDict
from langgraph.graph import StateGraph, END

class MortarState(TypedDict):
    serial_numbers: list[str]
    compliance_cleared: bool
    inspection_passed: bool

def validate_compliance(state: MortarState):
    # Simulate legal and export check
    return {'compliance_cleared': True}

def conduct_ballistic_inspection(state: MortarState):
    # Simulate hardware verification
    return {'inspection_passed': True}

graph = StateGraph(MortarState)
graph.add_node('compliance', validate_compliance)
graph.add_node('inspection', conduct_ballistic_inspection)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'inspection')
graph.add_edge('inspection', END)
graph = graph.compile()

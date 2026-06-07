from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ShotgunProcessState(TypedDict):
    serial_number: str
    compliance_cleared: bool
    inspection_passed: bool

def verify_permit(state: ShotgunProcessState):
    # Simulate regulatory check
    return {'compliance_cleared': True}

def perform_inspection(state: ShotgunProcessState):
    # Simulate mechanical safety check
    return {'inspection_passed': True}

graph = StateGraph(ShotgunProcessState)
graph.add_node('verify_permit', verify_permit)
graph.add_node('inspect', perform_inspection)
graph.set_entry_point('verify_permit')
graph.add_edge('verify_permit', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()

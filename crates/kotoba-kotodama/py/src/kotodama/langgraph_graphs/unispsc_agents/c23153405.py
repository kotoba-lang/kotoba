from typing import TypedDict
from langgraph.graph import StateGraph, END

class LaserPartState(TypedDict):
    part_id: str
    spec_check: bool
    export_control_verified: bool

def validate_optics(state: LaserPartState):
    # Simulate CAD/spec validation logic for optical components
    state['spec_check'] = True
    return state

def check_export_compliance(state: LaserPartState):
    # Check dual-use export control status
    state['export_control_verified'] = True
    return state

graph = StateGraph(LaserPartState)
graph.add_node('validate', validate_optics)
graph.add_node('compliance', check_export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

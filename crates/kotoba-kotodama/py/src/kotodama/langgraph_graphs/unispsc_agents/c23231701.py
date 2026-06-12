from typing import TypedDict
from langgraph.graph import StateGraph, END

class LaserProcurementState(TypedDict):
    spec_compliance: bool
    safety_check: bool
    export_control_verified: bool

def validate_specs(state: LaserProcurementState):
    state['spec_compliance'] = True
    return state

def check_safety(state: LaserProcurementState):
    state['safety_check'] = True
    return state

def check_export(state: LaserProcurementState):
    state['export_control_verified'] = True
    return state

graph = StateGraph(LaserProcurementState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('check_safety', check_safety)
graph.add_node('check_export', check_export)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'check_safety')
graph.add_edge('check_safety', 'check_export')
graph.add_edge('check_export', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class MotorICState(TypedDict):
    part_number: str
    spec_sheet_url: str
    compliance_cleared: bool
    is_dual_use: bool

def validate_specs(state: MotorICState):
    # Simulate CAD/Spec validation for motor ICs
    state['compliance_cleared'] = True
    return state

def check_export_control(state: MotorICState):
    # Business logic for checking dual-use status
    state['is_dual_use'] = True
    return state

graph = StateGraph(MotorICState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_control)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()

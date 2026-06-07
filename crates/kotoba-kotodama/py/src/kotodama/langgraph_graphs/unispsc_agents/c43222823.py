from typing import TypedDict
from langgraph.graph import StateGraph, END

class WDMProcurementState(TypedDict):
    part_number: str
    spec_sheet_verified: bool
    compliance_check: bool
    export_control_cleared: bool

def validate_specs(state: WDMProcurementState):
    state['spec_sheet_verified'] = True
    return state

def check_compliance(state: WDMProcurementState):
    state['compliance_check'] = True
    return state

def check_export_controls(state: WDMProcurementState):
    state['export_control_cleared'] = True
    return state

graph = StateGraph(WDMProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_node('export', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', 'export')
graph.add_edge('export', END)
graph = graph.compile()

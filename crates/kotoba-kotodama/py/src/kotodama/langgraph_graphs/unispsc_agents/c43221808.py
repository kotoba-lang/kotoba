from typing import TypedDict
from langgraph.graph import StateGraph, END

class SDHProcurementState(TypedDict):
    spec_compliance: bool
    export_control_check: bool
    final_approval: bool

def validate_specs(state: SDHProcurementState):
    state['spec_compliance'] = True
    return state

def check_export_controls(state: SDHProcurementState):
    state['export_control_check'] = True
    return state

def approve_procurement(state: SDHProcurementState):
    state['final_approval'] = state['spec_compliance'] and state['export_control_check']
    return state

graph = StateGraph(SDHProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_controls)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

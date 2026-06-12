from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material: str
    inspection_passed: bool
    compliance_checked: bool

def validate_titanium_specs(state: ProcurementState):
    # Simulate geometric/metallurgical validation logic
    state['inspection_passed'] = True
    return state

def check_export_controls(state: ProcurementState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_titanium_specs)
graph.add_node('compliance', check_export_controls)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()

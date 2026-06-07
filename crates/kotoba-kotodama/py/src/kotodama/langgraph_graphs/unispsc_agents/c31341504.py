from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_specs: dict
    inspection_passed: bool
    compliance_risk: str

def validate_welding(state: ProcurementState):
    print('Validating welding integrity...')
    state['inspection_passed'] = True
    return state

def check_export_control(state: ProcurementState):
    print('Checking dual-use export compliance...')
    state['compliance_risk'] = 'Controlled'
    return state

graph = StateGraph(ProcurementState)
graph.add_node('weld_check', validate_welding)
graph.add_node('export_review', check_export_control)
graph.set_entry_point('weld_check')
graph.add_edge('weld_check', 'export_review')
graph.add_edge('export_review', END)
graph = graph.compile()

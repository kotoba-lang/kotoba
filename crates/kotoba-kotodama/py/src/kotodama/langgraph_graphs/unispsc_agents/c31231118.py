from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlloyProcurementState(TypedDict):
    alloy_grade: str
    dimensions: dict
    cert_passed: bool
    approved: bool

def validate_material(state: AlloyProcurementState):
    # Simulate chemical validation against ASTM/ASME standards
    state['cert_passed'] = 'Nickel' in state.get('alloy_grade', '')
    return state

def check_compliance(state: AlloyProcurementState):
    state['approved'] = state.get('cert_passed', False)
    return state

graph = StateGraph(AlloyProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()

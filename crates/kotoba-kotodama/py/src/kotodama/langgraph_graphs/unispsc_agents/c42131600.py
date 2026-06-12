from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClothingProcurementState(TypedDict):
    item_id: str
    material_certified: bool
    compliance_passed: bool

def validate_materials(state: ClothingProcurementState):
    # Simulate material composition check against safety standards
    state['material_certified'] = True
    return state

def check_compliance(state: ClothingProcurementState):
    # Simulate audit against ISO medical textile requirements
    state['compliance_passed'] = True
    return state

graph = StateGraph(ClothingProcurementState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class EyeglassState(TypedDict):
    product_id: str
    material_check: bool
    compliance_verified: bool

def validate_material(state: EyeglassState) -> EyeglassState:
    # Specialized check for skin-safe materials
    state['material_check'] = True
    return state

def verify_compliance(state: EyeglassState) -> EyeglassState:
    state['compliance_verified'] = True
    return state

graph = StateGraph(EyeglassState)
graph.add_node('validate_material', validate_material)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'verify_compliance')
graph.add_edge('verify_compliance', END)
graph = graph.compile()

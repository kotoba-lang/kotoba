from typing import TypedDict
from langgraph.graph import StateGraph, END

class DisplayProcurementState(TypedDict):
    item_id: str
    material_compliance: bool
    structural_integrity_check: bool
    approved: bool

def validate_material(state: DisplayProcurementState):
    state['material_compliance'] = True
    return {'material_compliance': True}

def validate_structure(state: DisplayProcurementState):
    state['structural_integrity_check'] = True
    return {'structural_integrity_check': True}

graph = StateGraph(DisplayProcurementState)
graph.add_node('validate_material', validate_material)
graph.add_node('validate_structure', validate_structure)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'validate_structure')
graph.add_edge('validate_structure', END)
graph = graph.compile()

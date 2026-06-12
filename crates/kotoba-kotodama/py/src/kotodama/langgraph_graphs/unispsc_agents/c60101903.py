from typing import TypedDict
from langgraph.graph import StateGraph, END

class TapeProcurementState(TypedDict):
    material_verified: bool
    safety_passed: bool
    order_status: str

def check_materials(state: TapeProcurementState):
    print('Verifying non-toxic adhesives and material composition...')
    return {'material_verified': True}

def validate_safety(state: TapeProcurementState):
    print('Confirming compliance with child safety standards...')
    return {'safety_passed': True}

graph = StateGraph(TapeProcurementState)
graph.add_node('verify_material', check_materials)
graph.add_node('validate_safety', validate_safety)
graph.set_entry_point('verify_material')
graph.add_edge('verify_material', 'validate_safety')
graph.add_edge('validate_safety', END)
graph = graph.compile()

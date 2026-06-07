from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_details: dict
    validation_passed: bool
    compliance_errors: List[str]

def validate_material(state: ProcurementState):
    material = state.get('item_details', {}).get('material', '')
    if material not in ['wood', 'plastic']:
        return {'validation_passed': False, 'compliance_errors': ['Invalid material type']}
    return {'validation_passed': True}

def check_safety_standards(state: ProcurementState):
    if not state.get('item_details', {}).get('is_non_toxic', False):
        return {'validation_passed': False, 'compliance_errors': ['Safety certification missing']}
    return {'validation_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_safety', check_safety_standards)
graph.add_edge('validate_material', 'check_safety')
graph.add_edge('check_safety', END)
graph.set_entry_point('validate_material')
graph = graph.compile()

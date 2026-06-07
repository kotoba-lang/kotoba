from typing import TypedDict
from langgraph.graph import StateGraph, END

class PillowProcurementState(TypedDict):
    pillow_type: str
    material_compliance: bool
    safety_check_passed: bool

def validate_material(state: PillowProcurementState):
    state['material_compliance'] = len(state.get('pillow_type', '')) > 0
    return state

def safety_inspection(state: PillowProcurementState):
    state['safety_check_passed'] = state['material_compliance']
    return state

graph = StateGraph(PillowProcurementState)
graph.add_node('validate_material', validate_material)
graph.add_node('safety_inspection', safety_inspection)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'safety_inspection')
graph.add_edge('safety_inspection', END)
graph = graph.compile()

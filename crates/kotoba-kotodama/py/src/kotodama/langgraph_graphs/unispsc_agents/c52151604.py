from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    material_compliance: bool
    passed_safety_check: bool

def validate_material(state: KitchenwareState):
    state['material_compliance'] = True
    return state

def check_quality(state: KitchenwareState):
    state['passed_safety_check'] = state.get('material_compliance', False)
    return state

graph = StateGraph(KitchenwareState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_quality', check_quality)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_quality')
graph.add_edge('check_quality', END)
graph = graph.compile()

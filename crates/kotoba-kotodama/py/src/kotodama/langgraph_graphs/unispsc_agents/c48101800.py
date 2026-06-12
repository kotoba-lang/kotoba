from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    item_name: str
    material_certified: bool
    safety_specs: List[str]
    validation_complete: bool

def validate_materials(state: KitchenwareState):
    state['material_certified'] = True
    return state

def check_safety_compliance(state: KitchenwareState):
    state['validation_complete'] = True
    return state

graph = StateGraph(KitchenwareState)
graph.add_node('material_validation', validate_materials)
graph.add_node('safety_check', check_safety_compliance)
graph.set_entry_point('material_validation')
graph.add_edge('material_validation', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()

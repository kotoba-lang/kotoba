from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    material_certified: bool
    safety_compliant: bool
    ready_for_procurement: bool

def validate_material(state: KitchenwareState):
    state['material_certified'] = True
    return state

def check_safety_standards(state: KitchenwareState):
    state['safety_compliant'] = True
    return state

def finalize_approval(state: KitchenwareState):
    state['ready_for_procurement'] = state['material_certified'] and state['safety_compliant']
    return state

graph = StateGraph(KitchenwareState)
graph.add_node('validate', validate_material)
graph.add_node('safety', check_safety_standards)
graph.add_node('finalize', finalize_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

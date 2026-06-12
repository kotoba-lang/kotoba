from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToothbrushState(TypedDict):
    material_compliance: bool
    safety_certification: bool
    approved: bool

def validate_material(state: ToothbrushState):
    return {'material_compliance': True}

def validate_safety(state: ToothbrushState):
    state['safety_certification'] = True
    state['approved'] = state['material_compliance'] and state['safety_certification']
    return state

graph = StateGraph(ToothbrushState)
graph.add_node('validate_material', validate_material)
graph.add_node('validate_safety', validate_safety)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'validate_safety')
graph.add_edge('validate_safety', END)
graph = graph.compile()

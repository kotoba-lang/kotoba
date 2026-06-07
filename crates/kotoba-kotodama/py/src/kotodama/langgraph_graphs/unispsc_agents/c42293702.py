from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalToolState(TypedDict):
    material_certified: bool
    sterilization_verified: bool
    quality_score: float

def validate_material(state: SurgicalToolState):
    state['material_certified'] = True
    return state

def check_sterilization(state: SurgicalToolState):
    state['sterilization_verified'] = True
    return state

graph = StateGraph(SurgicalToolState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_sterilization', check_sterilization)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_sterilization')
graph.add_edge('check_sterilization', END)
graph = graph.compile()

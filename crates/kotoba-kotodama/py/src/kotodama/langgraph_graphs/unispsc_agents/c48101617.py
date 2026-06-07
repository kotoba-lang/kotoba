from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShovelState(TypedDict):
    material_certified: bool
    max_load: float
    status: str

def validate_material(state: ShovelState):
    return {'material_certified': True if state.get('material_certified') else False}

def check_durability(state: ShovelState):
    load = state.get('max_load', 0)
    return {'status': 'Approved' if load > 0 else 'Rejected'}

graph = StateGraph(ShovelState)
graph.add_node('ValidateMaterial', validate_material)
graph.add_node('CheckDurability', check_durability)
graph.set_entry_point('ValidateMaterial')
graph.add_edge('ValidateMaterial', 'CheckDurability')
graph.add_edge('CheckDurability', END)
graph = graph.compile()

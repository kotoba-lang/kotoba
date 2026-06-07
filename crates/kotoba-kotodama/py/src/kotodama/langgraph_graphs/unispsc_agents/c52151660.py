from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    material_certified: bool
    heat_rating_celcius: int
    is_approved: bool

def validate_material(state: KitchenwareState):
    state['material_certified'] = True
    return state

def check_heat_rating(state: KitchenwareState):
    state['is_approved'] = state.get('heat_rating_celcius', 0) >= 200
    return state

graph = StateGraph(KitchenwareState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_heat_rating', check_heat_rating)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_heat_rating')
graph.add_edge('check_heat_rating', END)
graph = graph.compile()

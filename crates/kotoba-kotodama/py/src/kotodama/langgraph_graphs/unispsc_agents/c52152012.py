from typing import TypedDict
from langgraph.graph import StateGraph, END

class IceTrayState(TypedDict):
    material: str
    food_safety_cert: bool
    dimension_check: bool

def validate_material(state: IceTrayState):
    print('Validating food-grade compliance...')
    return {'food_safety_cert': True}

def check_dimensions(state: IceTrayState):
    print('Verifying tray dimensions for freezer fit...')
    return {'dimension_check': True}

graph = StateGraph(IceTrayState)
graph.add_node('validate', validate_material)
graph.add_node('dimensions', check_dimensions)
graph.set_entry_point('validate')
graph.add_edge('validate', 'dimensions')
graph.add_edge('dimensions', END)
graph = graph.compile()

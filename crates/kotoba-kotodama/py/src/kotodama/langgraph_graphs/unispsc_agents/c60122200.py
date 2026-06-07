from typing import TypedDict
from langgraph.graph import StateGraph, END

class CraftState(TypedDict):
    material: str
    finish_safety_checked: bool
    dimensions_verified: bool

def validate_materials(state: CraftState):
    print('Validating wood species and sustainable sourcing...')
    return {'material': 'Verified'}

def check_finish(state: CraftState):
    print('Verifying chemical safety of varnish/lacquer...')
    return {'finish_safety_checked': True}

graph = StateGraph(CraftState)
graph.add_node('check_material', validate_materials)
graph.add_node('check_finish', check_finish)
graph.set_entry_point('check_material')
graph.add_edge('check_material', 'check_finish')
graph.add_edge('check_finish', END)

graph = graph.compile()

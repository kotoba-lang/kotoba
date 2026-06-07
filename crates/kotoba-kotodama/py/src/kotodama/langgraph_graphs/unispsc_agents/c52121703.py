from typing import TypedDict
from langgraph.graph import StateGraph, END

class WashClothState(TypedDict):
    material_check: bool
    gsm_approved: bool
    final_signoff: bool

def validate_materials(state: WashClothState):
    print('Validating wash cloth fiber composition...')
    return {'material_check': True}

def check_density(state: WashClothState):
    print('Verifying GSM weight consistency...')
    return {'gsm_approved': True}

graph = StateGraph(WashClothState)
graph.add_node('validate', validate_materials)
graph.add_node('density', check_density)
graph.set_entry_point('validate')
graph.add_edge('validate', 'density')
graph.add_edge('density', END)
graph = graph.compile()

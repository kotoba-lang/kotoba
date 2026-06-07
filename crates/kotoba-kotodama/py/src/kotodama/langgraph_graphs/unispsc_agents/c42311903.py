from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrainState(TypedDict):
    material_compliance: bool
    sterility_verified: bool
    meets_biocompatibility: bool

def validate_materials(state: DrainState):
    return {'material_compliance': True}

def check_sterility(state: DrainState):
    return {'sterility_verified': True}

graph = StateGraph(DrainState)
graph.add_node('validate', validate_materials)
graph.add_node('sterility', check_sterility)
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph.set_entry_point('validate')
graph = graph.compile()

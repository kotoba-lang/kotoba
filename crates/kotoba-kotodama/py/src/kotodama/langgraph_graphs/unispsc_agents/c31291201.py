from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    part_id: str
    tolerance_check: bool
    material_certified: bool

def validate_specs(state: ExtrusionState):
    state['tolerance_check'] = True
    return state

def check_material(state: ExtrusionState):
    state['material_certified'] = True
    return state

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_specs)
graph.add_node('certify', check_material)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()

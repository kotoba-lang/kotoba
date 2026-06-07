from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    material_compliance: bool
    dimensional_check: bool
    approved: bool

def validate_materials(state: ExtrusionState):
    state['material_compliance'] = True
    return state

def check_dimensions(state: ExtrusionState):
    state['dimensional_check'] = True
    state['approved'] = state['material_compliance'] and state['dimensional_check']
    return state

graph = StateGraph(ExtrusionState)
graph.add_node('check_material', validate_materials)
graph.add_node('check_specs', check_dimensions)
graph.set_entry_point('check_material')
graph.add_edge('check_material', 'check_specs')
graph.add_edge('check_specs', END)
graph = graph.compile()

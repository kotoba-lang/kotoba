from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    material_certified: bool
    tolerance_checked: bool
    machining_validated: bool

def validate_material(state: CastState):
    state['material_certified'] = True
    return state

def check_tolerances(state: CastState):
    state['tolerance_checked'] = True
    return state

def validate_machining(state: CastState):
    state['machining_validated'] = True
    return state

graph = StateGraph(CastState)
graph.add_node('material', validate_material)
graph.add_node('tolerance', check_tolerances)
graph.add_node('machining', validate_machining)
graph.set_entry_point('material')
graph.add_edge('material', 'tolerance')
graph.add_edge('tolerance', 'machining')
graph.add_edge('machining', END)
graph = graph.compile()

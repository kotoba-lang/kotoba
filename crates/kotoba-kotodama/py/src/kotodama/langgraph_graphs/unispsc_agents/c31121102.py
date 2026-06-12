from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    material_certified: bool
    tolerance_checked: bool
    final_approval: bool

def validate_material(state: CastState) -> CastState:
    state['material_certified'] = True
    return state

def check_tolerances(state: CastState) -> CastState:
    state['tolerance_checked'] = True
    return state

graph = StateGraph(CastState)
graph.add_node('material', validate_material)
graph.add_node('tolerance', check_tolerances)
graph.set_entry_point('material')
graph.add_edge('material', 'tolerance')
graph.add_edge('tolerance', END)
graph = graph.compile()

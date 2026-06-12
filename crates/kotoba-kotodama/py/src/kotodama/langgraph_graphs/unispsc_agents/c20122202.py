from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    material_certified: bool
    tolerance_ok: bool
    load_verified: bool
    status: str

def validate_material(state: BearingState) -> BearingState:
    # Simulate material composition check
    state['material_certified'] = True
    return state

def validate_tolerance(state: BearingState) -> BearingState:
    # Simulate dimensional tolerance check
    state['tolerance_ok'] = True
    return state

def check_load_rating(state: BearingState) -> BearingState:
    # Simulate load rating verification
    state['load_verified'] = True
    state['status'] = 'COMPLETED'
    return state

graph = StateGraph(BearingState)
graph.add_node('material', validate_material)
graph.add_node('tolerance', validate_tolerance)
graph.add_node('load', check_load_rating)
graph.add_edge('material', 'tolerance')
graph.add_edge('tolerance', 'load')
graph.add_edge('load', END)
graph.set_entry_point('material')
graph = graph.compile()

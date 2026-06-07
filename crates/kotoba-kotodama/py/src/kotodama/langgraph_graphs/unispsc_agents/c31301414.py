from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    part_id: str
    tolerance_check: bool
    material_certified: bool

def validate_dimensions(state: ForgingState) -> ForgingState:
    state['tolerance_check'] = True
    return state

def check_certification(state: ForgingState) -> ForgingState:
    state['material_certified'] = True
    return state

graph = StateGraph(ForgingState)
graph.add_node('validate_dims', validate_dimensions)
graph.add_node('check_certs', check_certification)
graph.set_entry_point('validate_dims')
graph.add_edge('validate_dims', 'check_certs')
graph.add_edge('check_certs', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class OpthalmometerState(TypedDict):
    part_id: str
    material_certified: bool
    tolerance_check: bool

def validate_materials(state: OpthalmometerState):
    state['material_certified'] = True
    return state

def validate_tolerances(state: OpthalmometerState):
    state['tolerance_check'] = True
    return state

graph = StateGraph(OpthalmometerState)
graph.add_node('material_check', validate_materials)
graph.add_node('tolerance_check', validate_tolerances)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'tolerance_check')
graph.add_edge('tolerance_check', END)
graph = graph.compile()

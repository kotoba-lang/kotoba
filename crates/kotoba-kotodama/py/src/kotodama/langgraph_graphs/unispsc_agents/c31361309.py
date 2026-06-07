from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    assembly_id: str
    material_certified: bool
    welding_pass: bool
    validation_score: float

def validate_material(state: AssemblyState) -> AssemblyState:
    state['material_certified'] = True
    return state

def check_welding_quality(state: AssemblyState) -> AssemblyState:
    state['welding_pass'] = True
    state['validation_score'] = 1.0
    return state

graph = StateGraph(AssemblyState)
graph.add_node('material_check', validate_material)
graph.add_node('weld_inspection', check_welding_quality)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'weld_inspection')
graph.add_edge('weld_inspection', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    part_id: str
    material_certified: bool
    inspection_passed: bool
    ready_for_assembly: bool

def validate_material(state: ForgingState):
    state['material_certified'] = True
    return state

def run_ndt_inspection(state: ForgingState):
    state['inspection_passed'] = True
    return state

graph = StateGraph(ForgingState)
graph.add_node('validate_material', validate_material)
graph.add_node('run_ndt_inspection', run_ndt_inspection)
graph.add_edge('validate_material', 'run_ndt_inspection')
graph.add_edge('run_ndt_inspection', END)
graph.set_entry_point('validate_material')

graph = graph.compile()

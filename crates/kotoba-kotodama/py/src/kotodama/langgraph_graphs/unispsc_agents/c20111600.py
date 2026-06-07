from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningPartsState(TypedDict):
    part_id: str
    material_certified: bool
    inspection_passed: bool
    is_approved: bool

def validate_material(state: MiningPartsState) -> MiningPartsState:
    # Logic to verify material specification from catalog
    state['material_certified'] = True
    return state

def run_inspection(state: MiningPartsState) -> MiningPartsState:
    # Logic for automated visual or sensor inspection
    state['inspection_passed'] = True
    return state

def check_approval(state: MiningPartsState) -> MiningPartsState:
    state['is_approved'] = state['material_certified'] and state['inspection_passed']
    return state

graph = StateGraph(MiningPartsState)
graph.add_node('validate_material', validate_material)
graph.add_node('run_inspection', run_inspection)
graph.add_node('check_approval', check_approval)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'run_inspection')
graph.add_edge('run_inspection', 'check_approval')
graph.add_edge('check_approval', END)

graph = graph.compile()

from langgraph.graph import StateGraph, END
from typing import TypedDict
class ProcessingState(TypedDict):
    part_id: str
    material_certified: bool
    weld_integrity_passed: bool
def validate_material(state: ProcessingState):
    state['material_certified'] = True
    return state
def validate_weld(state: ProcessingState):
    state['weld_integrity_passed'] = True
    return state
graph = StateGraph(ProcessingState)
graph.add_node('material_check', validate_material)
graph.add_node('weld_check', validate_weld)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'weld_check')
graph.add_edge('weld_check', END)
graph = graph.compile()

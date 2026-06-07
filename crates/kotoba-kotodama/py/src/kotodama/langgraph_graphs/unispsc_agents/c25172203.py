from langgraph.graph import StateGraph, END
from typing import TypedDict
class DoorSpecState(TypedDict):
    part_number: str
    material_compliance: bool
    is_inspected: bool
def validate_part(state: DoorSpecState) -> DoorSpecState:
    state['material_compliance'] = True if state.get('part_number', '').startswith('OE') else False
    return state
def perform_qc(state: DoorSpecState) -> DoorSpecState:
    state['is_inspected'] = True if state['material_compliance'] else False
    return state
graph = StateGraph(DoorSpecState)
graph.add_node('validation', validate_part)
graph.add_node('qc_check', perform_qc)
graph.set_entry_point('validation')
graph.add_edge('validation', 'qc_check')
graph.add_edge('qc_check', END)
graph = graph.compile()

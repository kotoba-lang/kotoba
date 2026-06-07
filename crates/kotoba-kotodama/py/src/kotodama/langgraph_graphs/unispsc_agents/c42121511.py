from typing import TypedDict
from langgraph.graph import StateGraph, END

class VetToolState(TypedDict):
    material: str
    is_autoclavable: bool
    validation_passed: bool

def validate_material(state: VetToolState) -> VetToolState:
    material = state.get('material', 'unknown')
    state['validation_passed'] = material in ['medical-grade-silicone', 'stainless-steel', 'synthetic-fabric']
    return state

def check_autoclave(state: VetToolState) -> VetToolState:
    if state.get('is_autoclavable', False):
        print('Validated for high-heat autoclaving processes.')
    return state

graph = StateGraph(VetToolState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_autoclave', check_autoclave)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_autoclave')
graph.add_edge('check_autoclave', END)

graph = graph.compile()

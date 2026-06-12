from typing import TypedDict
from langgraph.graph import StateGraph, END

class TrowelState(TypedDict):
    blade_material: str
    blade_length: float
    inspection_passed: bool

def validate_trowel_specs(state: TrowelState):
    # Basic validation logic for trowel quality
    valid_materials = ['steel', 'stainless steel', 'carbon steel']
    if state.get('blade_material').lower() in valid_materials and state.get('blade_length') > 0:
        return {**state, 'inspection_passed': True}
    return {**state, 'inspection_passed': False}

graph = StateGraph(TrowelState)
graph.add_node('validate', validate_trowel_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class DumbbellState(TypedDict):
    weight_kg: float
    material: str
    quality_check_passed: bool

def validate_weight(state: DumbbellState) -> DumbbellState:
    # Logic to confirm weight calibration
    state['quality_check_passed'] = state.get('weight_kg', 0) > 0
    return state

def check_material(state: DumbbellState) -> DumbbellState:
    # Logic to verify material durability
    if state.get('material') in ['cast-iron', 'rubber-coated', 'steel']:
        state['quality_check_passed'] = True
    return state

graph = StateGraph(DumbbellState)
graph.add_node('validate', validate_weight)
graph.add_node('material_check', check_material)
graph.add_edge('validate', 'material_check')
graph.add_edge('material_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

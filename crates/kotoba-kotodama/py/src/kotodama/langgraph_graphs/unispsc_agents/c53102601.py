from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClothingState(TypedDict):
    material: str
    flammability_test_passed: bool
    is_compliant: bool

def validate_material(state: ClothingState):
    # Business logic for textile safety check
    passed = state.get('material') in ['Cotton', 'Polyester-Blend']
    return {'is_compliant': passed}

def check_compliance(state: ClothingState):
    return 'compliant' if state['is_compliant'] and state['flammability_test_passed'] else 'rejected'

graph = StateGraph(ClothingState)
graph.add_node('validate', validate_material)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

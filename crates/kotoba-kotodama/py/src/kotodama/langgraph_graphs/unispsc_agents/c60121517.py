from typing import TypedDict
from langgraph.graph import StateGraph, END

class CharcoalState(TypedDict):
    material_type: str
    quality_index: float
    inspection_passed: bool

def validate_charcoal(state: CharcoalState):
    # Business logic for charcoal procurement verification
    is_valid = state.get('quality_index', 0) > 0.8
    return {'inspection_passed': is_valid}

def packaging_check(state: CharcoalState):
    # Logic for fragile good handling
    return {'inspection_passed': True}

graph = StateGraph(CharcoalState)
graph.add_node('validate', validate_charcoal)
graph.add_node('packaging', packaging_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'packaging')
graph.add_edge('packaging', END)
graph = graph.compile()

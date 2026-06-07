from langgraph.graph import StateGraph, END
from typing import TypedDict

class PottySeatState(TypedDict):
    material_safety: bool
    dimensions: dict
    approved: bool

def validate_safety(state: PottySeatState):
    state['approved'] = state.get('material_safety', False) and 'width' in state.get('dimensions', {})
    return state

graph = StateGraph(PottySeatState)
graph.add_node('safety_check', validate_safety)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()

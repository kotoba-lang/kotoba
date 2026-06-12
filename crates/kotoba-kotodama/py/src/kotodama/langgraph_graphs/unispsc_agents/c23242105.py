from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolingState(TypedDict):
    iso_code: str
    material_grade: str
    is_valid: bool

def validate_insert(state: ToolingState) -> ToolingState:
    # Logic to check ISO code and material specifications
    state['is_valid'] = state.get('iso_code', '').startswith('C')
    return state

def route_procurement(state: ToolingState) -> str:
    return 'valid' if state['is_valid'] else 'invalid'

graph = StateGraph(ToolingState)
graph.add_node('validation', validate_insert)
graph.set_entry_point('validation')
graph.add_edge('validation', END)

graph = graph.compile()

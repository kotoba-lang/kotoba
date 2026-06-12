from typing import TypedDict
from langgraph.graph import StateGraph, END

class BookcaseState(TypedDict):
    material: str
    dimensions: dict
    is_compliant: bool

def validate_materials(state: BookcaseState):
    state['is_compliant'] = state.get('material') in ['wood', 'steel', 'aluminum']
    return state

def check_dimensions(state: BookcaseState):
    if state.get('dimensions', {}).get('height', 0) > 250:
        state['is_compliant'] = False
    return state

graph = StateGraph(BookcaseState)
graph.add_node('validate', validate_materials)
graph.add_node('dimensions', check_dimensions)
graph.add_edge('validate', 'dimensions')
graph.add_edge('dimensions', END)
graph.set_entry_point('validate')

graph = graph.compile()

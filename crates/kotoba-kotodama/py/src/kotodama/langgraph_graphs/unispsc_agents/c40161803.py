from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FilterSpecState(TypedDict):
    grade: str
    diameter_mm: float
    validated: bool

def validate_specs(state: FilterSpecState):
    # Basic validation for lab-grade filter paper
    if state.get('diameter_mm', 0) > 0 and state.get('grade'):
        return {'validated': True}
    return {'validated': False}

graph = StateGraph(FilterSpecState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

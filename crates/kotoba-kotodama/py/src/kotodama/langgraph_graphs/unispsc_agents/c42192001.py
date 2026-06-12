from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExamTableState(TypedDict):
    specs: dict
    is_compliant: bool

def validate_ergonomics(state: ExamTableState):
    # Business logic for compliance verification
    height = state.get('specs', {}).get('height_range', 0)
    state['is_compliant'] = height > 500
    return state

graph = StateGraph(ExamTableState)
graph.add_node('validate', validate_ergonomics)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

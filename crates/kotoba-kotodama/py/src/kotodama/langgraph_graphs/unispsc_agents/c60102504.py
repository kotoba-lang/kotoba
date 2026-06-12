from typing import TypedDict
from langgraph.graph import StateGraph, END

class TextbookState(TypedDict):
    title: str
    grade_level: str
    compliance_check: bool
    approved: bool

def validate_curriculum(state: TextbookState) -> TextbookState:
    state['compliance_check'] = state.get('grade_level') is not None
    return state

def approval_step(state: TextbookState) -> TextbookState:
    state['approved'] = state['compliance_check'] == True
    return state

graph = StateGraph(TextbookState)
graph.add_node("validate", validate_curriculum)
graph.add_node("approve", approval_step)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()

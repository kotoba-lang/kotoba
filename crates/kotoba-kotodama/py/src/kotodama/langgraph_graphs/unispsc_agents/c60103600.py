from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    content_type: str
    cultural_compliance: bool
    is_approved: bool

def validate_cultural_content(state: ProcurementState):
    print('Validating multicultural materials for cultural sensitivity.')
    state['cultural_compliance'] = True
    return state

def approve_procurement(state: ProcurementState):
    state['is_approved'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validator', validate_cultural_content)
graph.add_node('approver', approve_procurement)
graph.add_edge('validator', 'approver')
graph.add_edge('approver', END)
graph.set_entry_point('validator')
graph = graph.compile()

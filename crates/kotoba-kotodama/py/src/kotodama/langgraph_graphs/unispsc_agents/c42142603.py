from typing import TypedDict
from langgraph.graph import StateGraph, END

class SyringeState(TypedDict):
    product_id: str
    compliance_checked: bool
    sterility_verified: bool

def validate_medical_grade(state: SyringeState) -> SyringeState:
    state['compliance_checked'] = True
    return state

def verify_sterility(state: SyringeState) -> SyringeState:
    state['sterility_verified'] = True
    return state

graph = StateGraph(SyringeState)
graph.add_node('validate', validate_medical_grade)
graph.add_node('sterility', verify_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()

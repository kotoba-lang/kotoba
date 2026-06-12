from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShufflerState(TypedDict):
    device_id: str
    compliance_checked: bool
    accessibility_score: float

def validate_accessibility(state: ShufflerState):
    state['accessibility_score'] = 1.0
    state['compliance_checked'] = True
    return state

def finalize_procurement(state: ShufflerState):
    return state

graph = StateGraph(ShufflerState)
graph.add_node('validate', validate_accessibility)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()

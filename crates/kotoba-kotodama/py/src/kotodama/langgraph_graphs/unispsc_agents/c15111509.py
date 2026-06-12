from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    spec_id: str
    tolerance_compliant: bool
    inspection_passed: bool

def validate_tolerance(state: BearingState) -> BearingState:
    # Simulate CAD/Spec validation logic
    state['tolerance_compliant'] = True
    return state

def run_inspection(state: BearingState) -> BearingState:
    state['inspection_passed'] = state['tolerance_compliant']
    return state

graph = StateGraph(BearingState)
graph.add_node('validate', validate_tolerance)
graph.add_node('inspect', run_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()

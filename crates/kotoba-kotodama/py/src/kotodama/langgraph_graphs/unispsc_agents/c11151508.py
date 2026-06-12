from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GaNState(TypedDict):
    purity: float
    inspection_passed: bool
    compliance_checked: bool

def validate_purity(state: GaNState) -> GaNState:
    state['inspection_passed'] = state.get('purity', 0) >= 99.999
    return state

def check_compliance(state: GaNState) -> GaNState:
    state['compliance_checked'] = True
    return state

graph = StateGraph(GaNState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

# The graph instance 'graph' is now compiled and ready for execution with state input

graph = graph.compile()

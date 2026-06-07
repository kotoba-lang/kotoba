from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MarkerState(TypedDict):
    marker_type: str
    ink_compliance: bool
    tip_quality_check: bool

def validate_ink(state: MarkerState) -> MarkerState:
    state['ink_compliance'] = True
    return state

def check_tip(state: MarkerState) -> MarkerState:
    state['tip_quality_check'] = True
    return state

graph = StateGraph(MarkerState)
graph.add_node('validate_ink', validate_ink)
graph.add_node('check_tip', check_tip)
graph.set_entry_point('validate_ink')
graph.add_edge('validate_ink', 'check_tip')
graph.add_edge('check_tip', END)
graph = graph.compile()

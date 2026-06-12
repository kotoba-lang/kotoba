from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity_cert: bool
    safety_check: bool
    approved: bool

def validate_quality(state: ProcurementState):
    state['purity_cert'] = True
    return state

def validate_safety(state: ProcurementState):
    state['safety_check'] = True
    return state

def final_check(state: ProcurementState):
    state['approved'] = state['purity_cert'] and state['safety_check']
    return state

graph = StateGraph(ProcurementState)
graph.add_node('quality', validate_quality)
graph.add_node('safety', validate_safety)
graph.add_node('final', final_check)

graph.set_entry_point('quality')
graph.add_edge('quality', 'safety')
graph.add_edge('safety', 'final')
graph.add_edge('final', END)
graph = graph.compile()

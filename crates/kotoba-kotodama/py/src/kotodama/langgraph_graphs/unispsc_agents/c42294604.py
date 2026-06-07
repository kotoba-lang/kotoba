from langgraph.graph import StateGraph, END
from typing import TypedDict

class FilterState(TypedDict):
    product_id: str
    compliance_checked: bool
    sterility_verified: bool

def validate_quality(state: FilterState):
    state['compliance_checked'] = True
    return state

def check_sterility(state: FilterState):
    state['sterility_verified'] = True
    return state

graph = StateGraph(FilterState)
graph.add_node('validate', validate_quality)
graph.add_node('sterility', check_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()

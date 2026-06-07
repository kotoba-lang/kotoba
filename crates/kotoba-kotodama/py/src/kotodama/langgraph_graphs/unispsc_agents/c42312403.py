from typing import TypedDict
from langgraph.graph import StateGraph, END

class WoundCareState(TypedDict):
    product_sku: str
    is_sterile: bool
    compliant: bool

def validate_certification(state: WoundCareState):
    state['compliant'] = state.get('is_sterile', False)
    return state

graph = StateGraph(WoundCareState)
graph.add_node('validate_cert', validate_certification)
graph.set_entry_point('validate_cert')
graph.add_edge('validate_cert', END)
graph = graph.compile()

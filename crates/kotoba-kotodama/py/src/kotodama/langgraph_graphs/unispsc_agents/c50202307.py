from typing import TypedDict
from langgraph.graph import StateGraph, END

class BeverageState(TypedDict):
    product_name: str
    quality_passed: bool
    expiry_valid: bool

def validate_quality(state: BeverageState):
    state['quality_passed'] = True
    return state

def check_expiry(state: BeverageState):
    state['expiry_valid'] = True
    return state

graph = StateGraph(BeverageState)
graph.add_node('validate_quality', validate_quality)
graph.add_node('check_expiry', check_expiry)
graph.set_entry_point('validate_quality')
graph.add_edge('validate_quality', 'check_expiry')
graph.add_edge('check_expiry', END)
graph = graph.compile()

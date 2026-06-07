from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class State(TypedDict):
    product_sku: str
    compliance_cleared: bool
    safety_check_passed: bool

def validate_pharma(state: State) -> State:
    # Logic to verify pharmaceutical compliance data
    state['compliance_cleared'] = True
    return state

def safety_audit(state: State) -> State:
    # Logic to verify dangerous goods/storage constraints
    state['safety_check_passed'] = True
    return state

graph = StateGraph(State)
graph.add_node('validate', validate_pharma)
graph.add_node('safety', safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

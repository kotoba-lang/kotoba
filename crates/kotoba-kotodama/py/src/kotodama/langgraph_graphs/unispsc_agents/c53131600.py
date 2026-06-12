from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProductState(TypedDict):
    product_name: str
    compliance_cleared: bool
    qc_passed: bool

def validate_ingredients(state: ProductState) -> ProductState:
    # Simulate regulatory check logic
    state['compliance_cleared'] = True
    return state

def run_quality_check(state: ProductState) -> ProductState:
    # Simulate Lab testing result simulation
    state['qc_passed'] = True
    return state

graph = StateGraph(ProductState)
graph.add_node('verify', validate_ingredients)
graph.add_node('qc', run_quality_check)
graph.set_entry_point('verify')
graph.add_edge('verify', 'qc')
graph.add_edge('qc', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class CleaningProductState(TypedDict):
    product_id: str
    material_safety_verified: bool
    optical_compatibility_test: bool

def check_msds(state: CleaningProductState):
    # Simulate MSDS verification logic
    return {'material_safety_verified': True}

def verify_compatibility(state: CleaningProductState):
    # Simulate lens coating compatibility assessment
    return {'optical_compatibility_test': True}

graph = StateGraph(CleaningProductState)
graph.add_node('check_msds', check_msds)
graph.add_node('verify_compatibility', verify_compatibility)
graph.set_entry_point('check_msds')
graph.add_edge('check_msds', 'verify_compatibility')
graph.add_edge('verify_compatibility', END)
graph = graph.compile()

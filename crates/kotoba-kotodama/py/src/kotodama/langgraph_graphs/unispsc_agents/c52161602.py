from typing import TypedDict
from langgraph.graph import StateGraph, END

class AVCleanerState(TypedDict):
    product_id: str
    sds_verified: bool
    is_safe_for_optics: bool

def check_chemical_safety(state: AVCleanerState):
    # Simulate SDS validation logic
    return {'sds_verified': True}

def validate_compatibility(state: AVCleanerState):
    # Simulate optical compatibility check
    return {'is_safe_for_optics': True}

graph_builder = StateGraph(AVCleanerState)
graph_builder.add_node('safety_check', check_chemical_safety)
graph_builder.add_node('compat_check', validate_compatibility)
graph_builder.add_edge('safety_check', 'compat_check')
graph_builder.add_edge('compat_check', END)
graph_builder.set_entry_point('safety_check')
graph = graph_builder.compile()

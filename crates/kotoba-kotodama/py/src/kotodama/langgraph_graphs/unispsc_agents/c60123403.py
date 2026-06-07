from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CraftSupplyState(TypedDict):
    item_name: str
    spec_check: bool
    safety_verified: bool

def validate_safety(state: CraftSupplyState):
    # Simulate safety compliance check for small craft parts
    return {'safety_verified': True}

def validate_specs(state: CraftSupplyState):
    # Simulate spec verification against procurement requirements
    return {'spec_check': True}

graph = StateGraph(CraftSupplyState)
graph.add_node('safety_check', validate_safety)
graph.add_node('spec_review', validate_specs)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'spec_review')
graph.add_edge('spec_review', END)
graph = graph.compile()

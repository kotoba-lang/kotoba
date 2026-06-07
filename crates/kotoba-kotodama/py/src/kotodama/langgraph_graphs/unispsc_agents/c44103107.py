from typing import TypedDict
from langgraph.graph import StateGraph, END

class CleaningSupplyState(TypedDict):
    supply_type: str
    sds_verified: bool
    compatibility_check: bool

def validate_sds(state: CleaningSupplyState):
    # Simulate SDS validation logic
    return {'sds_verified': True}

def check_compatibility(state: CleaningSupplyState):
    # Verify chemical solvent against equipment specs
    return {'compatibility_check': True}

graph = StateGraph(CleaningSupplyState)
graph.add_node('sds_check', validate_sds)
graph.add_node('comp_check', check_compatibility)
graph.add_edge('sds_check', 'comp_check')
graph.add_edge('comp_check', END)
graph.set_entry_point('sds_check')
graph = graph.compile()

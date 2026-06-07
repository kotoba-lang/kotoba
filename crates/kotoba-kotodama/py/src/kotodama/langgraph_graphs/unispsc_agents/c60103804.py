from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MapProcurementState(TypedDict):
    item_id: str
    provenance_verified: bool
    condition_score: float
    approved: bool

def check_provenance(state: MapProcurementState):
    print(f'Verifying provenance for map: {state[item_id]}')
    return {provenance_verified: True}

def assess_condition(state: MapProcurementState):
    print(f'Assessing physical condition for: {state[item_id]}')
    return {condition_score: 9.5}

def finalize_approval(state: MapProcurementState):
    is_approved = state[provenance_verified] and state[condition_score] > 8.0
    return {approved: is_approved}

graph = StateGraph(MapProcurementState)
graph.add_node('verify', check_provenance)
graph.add_node('assess', assess_condition)
graph.add_node('finalize', finalize_approval)
graph.set_entry_point('verify')
graph.add_edge('verify', 'assess')
graph.add_edge('assess', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

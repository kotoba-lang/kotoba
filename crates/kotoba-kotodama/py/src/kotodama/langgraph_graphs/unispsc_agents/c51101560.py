from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    purity_validated: bool
    temp_log_verified: bool
    hazard_check_passed: bool
    status: str

def validate_purity(state: ReagentState):
    # Simulate analytical validation logic
    return {'purity_validated': True, 'status': 'purity_check_passed'}

def verify_storage(state: ReagentState):
    return {'temp_log_verified': True, 'status': 'storage_check_passed'}

def hazard_clearance(state: ReagentState):
    return {'hazard_check_passed': True, 'status': 'cleared_for_release'}

graph = StateGraph(ReagentState)
graph.add_node('validate', validate_purity)
graph.add_node('storage', verify_storage)
graph.add_node('hazard', hazard_clearance)
graph.add_edge('validate', 'storage')
graph.add_edge('storage', 'hazard')
graph.add_edge('hazard', END)
graph.set_entry_point('validate')
graph = graph.compile()

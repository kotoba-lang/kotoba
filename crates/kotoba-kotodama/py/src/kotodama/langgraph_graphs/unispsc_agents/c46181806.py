from typing import TypedDict
from langgraph.graph import StateGraph, END

class LensCleanerState(TypedDict):
    spec_sheet_url: str
    is_compliant: bool
    hazard_rating: int

def validate_specs(state: LensCleanerState):
    # Simulate chemical safety check
    return {'is_compliant': True if state.get('hazard_rating', 0) < 3 else False}

def route_by_compliance(state: LensCleanerState):
    return 'approved' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(LensCleanerState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'approved': END, 'flag_for_review': END})
graph = graph.compile()

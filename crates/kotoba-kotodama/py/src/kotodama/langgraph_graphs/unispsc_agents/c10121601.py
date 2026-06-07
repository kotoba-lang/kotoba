from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class FeedSeedState(TypedDict):
    seed_type: str
    quality_metrics: dict
    compliance_checks: List[str]
    is_approved: bool

def validate_quality(state: FeedSeedState):
    metrics = state.get('quality_metrics', {})
    approved = metrics.get('purity', 0) > 95 and metrics.get('moisture', 0) < 13
    return {'is_approved': approved}

def perform_compliance_check(state: FeedSeedState):
    checks = ['non_gmo_verified', 'moisture_verified']
    return {'compliance_checks': checks}

graph = StateGraph(FeedSeedState)
graph.add_node('validate', validate_quality)
graph.add_node('compliance', perform_compliance_check)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'validate')
graph.add_edge('validate', END)
graph = graph.compile()

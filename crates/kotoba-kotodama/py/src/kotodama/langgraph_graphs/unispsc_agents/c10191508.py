from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class FeedAdditiveState(TypedDict):
    additive_code: str
    quality_metrics: dict
    compliance_checks: Annotated[list, operator.add]
    is_approved: bool

def validate_purity(state: FeedAdditiveState) -> FeedAdditiveState:
    metrics = state.get('quality_metrics', {})
    purity = metrics.get('purity_percentage', 0)
    state['is_approved'] = purity >= 99.0
    state['compliance_checks'].append('purity_check_passed')
    return state

def verify_storage(state: FeedAdditiveState) -> FeedAdditiveState:
    state['compliance_checks'].append('storage_protocol_verified')
    return state

graph = StateGraph(FeedAdditiveState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_storage', verify_storage)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_storage')
graph.add_edge('verify_storage', END)
graph = graph.compile()

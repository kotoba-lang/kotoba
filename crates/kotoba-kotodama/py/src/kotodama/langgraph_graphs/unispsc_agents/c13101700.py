from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CrudeOilState(TypedDict):
    commodity_id: str
    quality_metrics: dict
    compliance_checks: List[str]
    status: str

def validate_quality(state: CrudeOilState) -> CrudeOilState:
    metrics = state.get('quality_metrics', {})
    if metrics.get('sulfur_pct', 0) > 0.5:
        state['compliance_checks'].append('HIGH_SULFUR_FLAG')
    state['status'] = 'VALIDATED'
    return state

def route_procurement(state: CrudeOilState) -> str:
    if 'HIGH_SULFUR_FLAG' in state['compliance_checks']:
        return 'manual_review'
    return 'approve'

graph = StateGraph(CrudeOilState)
graph.add_node('validate', validate_quality)
graph.add_edge('validate', 'route')
graph.add_conditional_edges('route', route_procurement, {'manual_review': 'review', 'approve': END})
graph.add_node('review', lambda x: x)
graph.add_edge('review', END)
graph.set_entry_point('validate')

graph = graph.compile()

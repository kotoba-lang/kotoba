from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CrudeState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    security_clearance: bool
    approved: bool

def validate_quality(state: CrudeState) -> CrudeState:
    # Logic for checking API gravity and sulfur
    metrics = state.get('quality_metrics', {})
    state['approved'] = metrics.get('sulfur_content', 1.0) < 0.5
    return state

def check_security(state: CrudeState) -> CrudeState:
    # Logic for sanctions check
    state['security_clearance'] = True
    return state

graph = StateGraph(CrudeState)
graph.add_node('validate_quality', validate_quality)
graph.add_node('check_security', check_security)
graph.set_entry_point('validate_quality')
graph.add_edge('validate_quality', 'check_security')
graph.add_edge('check_security', END)
graph = graph.compile()

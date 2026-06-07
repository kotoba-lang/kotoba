from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class JuiceState(TypedDict):
    juice_type: str
    quality_metrics: dict
    approved: bool

def validate_quality(state: JuiceState):
    metrics = state.get('quality_metrics', {})
    is_approved = metrics.get('brix', 0) > 10 and metrics.get('temp', 0) < 5
    return {'approved': is_approved}

def process_shipment(state: JuiceState):
    return {'approved': True}

graph = StateGraph(JuiceState)
graph.add_node('validate', validate_quality)
graph.add_node('ship', process_shipment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'ship')
graph.add_edge('ship', END)
graph = graph.compile()

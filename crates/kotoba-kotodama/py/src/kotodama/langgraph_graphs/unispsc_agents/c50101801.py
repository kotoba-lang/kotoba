from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProduceState(TypedDict):
    fruit_type: str
    quality_metrics: dict
    approved: bool

def validate_freshness(state: ProduceState):
    # Basic logic for checking clementine quality flags
    metrics = state.get('quality_metrics', {})
    is_fresh = metrics.get('brix', 0) >= 10 and metrics.get('days_post_harvest', 0) < 7
    return {'approved': is_fresh}

workflow = StateGraph(ProduceState)
workflow.add_node('validate', validate_freshness)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()

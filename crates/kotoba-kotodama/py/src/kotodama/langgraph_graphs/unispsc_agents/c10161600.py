from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FeedState(TypedDict):
    commodity_id: str
    quality_metrics: dict
    approved: bool
    logs: List[str]

def validate_metrics(state: FeedState):
    metrics = state.get('quality_metrics', {})
    is_valid = metrics.get('protein_content', 0) > 12.0
    return {'approved': is_valid, 'logs': ['Validated nutritional metrics']}

def generate_procurement_order(state: FeedState):
    if state['approved']:
        return {'logs': ['Procurement order generated']}
    return {'logs': ['Procurement order rejected due to low quality']}

builder = StateGraph(FeedState)
builder.add_node('validate', validate_metrics)
builder.add_node('order', generate_procurement_order)
builder.set_entry_point('validate')
builder.add_edge('validate', 'order')
builder.add_edge('order', END)
graph = builder.compile()

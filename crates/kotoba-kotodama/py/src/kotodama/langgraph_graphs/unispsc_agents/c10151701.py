from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class LivestockFeedState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    inspection_status: str
    delivery_approved: bool

def validate_nutritional_compliance(state: LivestockFeedState) -> LivestockFeedState:
    # Simulate complex nutritional validation logic
    metrics = state.get('quality_metrics', {})
    is_valid = metrics.get('protein_content', 0) > 15.0
    return {'inspection_status': 'passed' if is_valid else 'failed', 'delivery_approved': is_valid}

def update_inventory_status(state: LivestockFeedState) -> LivestockFeedState:
    return {'inspection_status': 'inventory_updated', 'delivery_approved': True}

# Compile the graph
workflow = StateGraph(LivestockFeedState)
workflow.add_node('validate', validate_nutritional_compliance)
workflow.add_node('inventory', update_inventory_status)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'inventory')
workflow.add_edge('inventory', END)
graph = workflow.compile()

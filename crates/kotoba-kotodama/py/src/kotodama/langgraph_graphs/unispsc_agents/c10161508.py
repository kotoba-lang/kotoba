from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FeedState(TypedDict):
    batch_id: str
    quality_status: str
    quarantine_checked: bool
    history: Annotated[Sequence[str], operator.add]

def validate_batch(state: FeedState):
    # Simulate quality inspection logic
    status = 'passed' if state.get('quarantine_checked', False) else 'failed'
    return {'quality_status': status, 'history': ['validated_batch']}

def update_inventory(state: FeedState):
    return {'history': ['inventory_updated']}

graph = StateGraph(FeedState)
graph.add_node('validate', validate_batch)
graph.add_node('inventory', update_inventory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph = graph.compile()

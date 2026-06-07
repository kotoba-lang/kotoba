from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FeedState(TypedDict):
    feed_type: str
    quality_metrics: dict
    approved: bool
    history: Annotated[Sequence[str], operator.add]

def validate_nutrition(state: FeedState) -> FeedState:
    # Logic for nutrient compliance check
    metrics = state.get('quality_metrics', {})
    is_valid = metrics.get('protein', 0) > 15.0
    return {'approved': is_valid, 'history': ['Validated nutrition']}

def check_contamination(state: FeedState) -> FeedState:
    # Logic for safety/microbial check
    return {'approved': state['approved'] and True, 'history': ['Checked contamination']}

graph = StateGraph(FeedState)
graph.add_node('validate', validate_nutrition)
graph.add_node('safety', check_contamination)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()

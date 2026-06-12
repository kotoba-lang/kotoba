from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FeedState(TypedDict):
    order_id: str
    material_spec: dict
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_feed_quality(state: FeedState):
    spec = state.get('material_spec', {})
    moisture = spec.get('moisture_content', 0)
    if moisture > 15:
        return {'validation_log': ['Moisture too high'], 'status': 'rejected'}
    return {'validation_log': ['Quality check passed'], 'status': 'validated'}

def route_feed_order(state: FeedState):
    if state['status'] == 'validated':
        return 'procure'
    return END

def procure_feed(state: FeedState):
    return {'validation_log': ['Procurement initialized']}

graph = StateGraph(FeedState)
graph.add_node('validate', validate_feed_quality)
graph.add_node('procure', procure_feed)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_feed_order, {'procure': 'procure', END: END})
graph.add_edge('procure', END)
graph = graph.compile()

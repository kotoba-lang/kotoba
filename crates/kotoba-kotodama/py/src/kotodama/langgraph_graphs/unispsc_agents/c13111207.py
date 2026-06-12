from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CrudeState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    shipping_status: str
    validation_log: Annotated[Sequence[str], add_messages]

def validate_crude_metrics(state: CrudeState):
    metrics = state.get('quality_metrics', {})
    if metrics.get('sulfur', 0) > 2.5:
        return {'validation_log': ['High sulfur content detected - requires specialized refining.']}
    return {'validation_log': ['Quality check passed.']}

def process_logistics(state: CrudeState):
    return {'shipping_status': 'Cleared for transport with containment protocols.'}

graph = StateGraph(CrudeState)
graph.add_node('validate', validate_crude_metrics)
graph.add_node('logistics', process_logistics)
graph.set_entry_point('validate')
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()

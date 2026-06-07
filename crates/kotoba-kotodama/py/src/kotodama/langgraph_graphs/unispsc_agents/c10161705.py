from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class LivestockState(TypedDict):
    commodity_id: str
    quality_checks: List[str]
    approved: bool

def validate_livestock_batch(state: LivestockState):
    checks = state.get('quality_checks', [])
    is_approved = len(checks) >= 3
    return {'approved': is_approved}

def route_by_approval(state: LivestockState):
    return 'process' if state['approved'] else END

def process_livestock(state: LivestockState):
    print('Processing certified livestock batch')
    return {'commodity_id': state['commodity_id']}

graph = StateGraph(LivestockState)
graph.add_node('validate', validate_livestock_batch)
graph.add_node('process', process_livestock)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_approval)
graph.add_edge('process', END)
graph = graph.compile()

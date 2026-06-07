from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LiveBioState(TypedDict):
    specimen_id: str
    health_status: str
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_health_protocols(state: LiveBioState) -> LiveBioState:
    if not state.get('health_status'):
        return {**state, 'validation_logs': ['Error: Missing health status']}
    return {**state, 'validation_logs': ['Protocol validated']}

def route_to_quarantine(state: LiveBioState) -> str:
    if state.get('health_status') == 'pending':
        return 'quarantine_node'
    return 'process_node'

graph = StateGraph(LiveBioState)
graph.add_node('validate', validate_health_protocols)
graph.add_node('quarantine_node', lambda s: s)
graph.add_node('process_node', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_to_quarantine)
graph.add_edge('quarantine_node', END)
graph.add_edge('process_node', END)
graph = graph.compile()

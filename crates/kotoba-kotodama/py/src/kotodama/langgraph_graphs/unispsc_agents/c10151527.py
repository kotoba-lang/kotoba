from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class DrillingState(TypedDict):
    depth: float
    geology_type: str
    status: str
    logs: Annotated[Sequence[str], add_messages]

def validate_geology(state: DrillingState) -> DrillingState:
    if not state.get('geology_type'):
        return {**state, 'status': 'FAILED: Geology type required'}
    return {**state, 'status': 'GEOLOGY_VALIDATED'}

def execute_drill(state: DrillingState) -> DrillingState:
    if state.get('status') == 'GEOLOGY_VALIDATED':
        return {**state, 'status': 'DRILLING_IN_PROGRESS', 'logs': ['Starting drill rotation', 'Initiating core sampling']}
    return {**state, 'status': 'DRILL_ABORTED'}

graph = StateGraph(DrillingState)
graph.add_node('validate', validate_geology)
graph.add_node('drill', execute_drill)
graph.add_edge('validate', 'drill')
graph.add_edge('drill', END)
graph.set_entry_point('validate')
graph = graph.compile()

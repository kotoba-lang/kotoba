from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ContainerState(TypedDict):
    container_id: str
    is_sterile: bool
    media_check: bool
    approved: bool

def validate_sterility(state: ContainerState):
    state['is_sterile'] = True
    return state

def validate_media(state: ContainerState):
    state['media_check'] = True
    return state

def finalize_check(state: ContainerState):
    state['approved'] = state['is_sterile'] and state['media_check']
    return state

graph = StateGraph(ContainerState)
graph.add_node('sterile_check', validate_sterility)
graph.add_node('media_check', validate_media)
graph.add_node('finalizer', finalize_check)
graph.add_edge('sterile_check', 'media_check')
graph.add_edge('media_check', 'finalizer')
graph.add_edge('finalizer', END)
graph.set_entry_point('sterile_check')

graph = graph.compile()

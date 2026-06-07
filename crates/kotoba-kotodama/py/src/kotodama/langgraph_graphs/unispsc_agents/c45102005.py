from typing import TypedDict
from langgraph.graph import StateGraph, END

class PhotoSettingState(TypedDict):
    machine_id: str
    resolution_check: bool
    media_compatibility: bool

def validate_specs(state: PhotoSettingState):
    # Simulate validation logic for high-end typesetting units
    state['resolution_check'] = True
    return state

def check_compatibility(state: PhotoSettingState):
    state['media_compatibility'] = True
    return state

graph = StateGraph(PhotoSettingState)
graph.add_node('validate', validate_specs)
graph.add_node('compatible', check_compatibility)
graph.add_edge('validate', 'compatible')
graph.add_edge('compatible', END)
graph.set_entry_point('validate')
graph = graph.compile()

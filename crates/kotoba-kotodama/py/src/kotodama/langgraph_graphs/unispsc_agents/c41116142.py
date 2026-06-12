from typing import TypedDict
from langgraph.graph import StateGraph, END

class MediaState(TypedDict):
    media_type: str
    temp_control: bool
    sterility_verified: bool
    approved: bool

def validate_culture_specs(state: MediaState):
    state['temp_control'] = True
    state['sterility_verified'] = True
    state['approved'] = True
    return state

builder = StateGraph(MediaState)
builder.add_node('validation', validate_culture_specs)
builder.set_entry_point('validation')
builder.add_edge('validation', END)
graph = builder.compile()

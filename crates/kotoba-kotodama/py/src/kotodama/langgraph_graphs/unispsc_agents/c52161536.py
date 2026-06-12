from typing import TypedDict
from langgraph.graph import StateGraph, END

class MDState(TypedDict):
    device_id: str
    sampling_check: bool
    codec_validation: bool
    is_approved: bool

def check_audio_specs(state: MDState) -> MDState:
    state['sampling_check'] = True
    return state

def validate_codec(state: MDState) -> MDState:
    state['codec_validation'] = True
    return state

def finalize_compliance(state: MDState) -> MDState:
    state['is_approved'] = state['sampling_check'] and state['codec_validation']
    return state

graph = StateGraph(MDState)
graph.add_node('check_sampling', check_audio_specs)
graph.add_node('check_codec', validate_codec)
graph.add_node('final_approval', finalize_compliance)
graph.set_entry_point('check_sampling')
graph.add_edge('check_sampling', 'check_codec')
graph.add_edge('check_codec', 'final_approval')
graph.add_edge('final_approval', END)
graph = graph.compile()

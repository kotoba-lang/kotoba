from typing import TypedDict
from langgraph.graph import StateGraph, END

class HeadframeState(TypedDict):
    frame_id: str
    compliance_ok: bool
    imaging_valid: bool

def validate_specs(state: HeadframeState):
    state['compliance_ok'] = True
    return state

def check_imaging_compatibility(state: HeadframeState):
    state['imaging_valid'] = True
    return state

graph = StateGraph(HeadframeState)
graph.add_node('validate', validate_specs)
graph.add_node('imaging', check_imaging_compatibility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'imaging')
graph.add_edge('imaging', END)
graph = graph.compile()

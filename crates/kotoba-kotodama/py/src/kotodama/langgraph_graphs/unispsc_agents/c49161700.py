from typing import TypedDict
from langgraph.graph import StateGraph, END

class TrackEquipmentState(TypedDict):
    equipment_id: str
    specs_verified: bool
    certification_valid: bool

def validate_specs(state: TrackEquipmentState):
    state['specs_verified'] = True
    return state

def check_certification(state: TrackEquipmentState):
    state['certification_valid'] = True
    return state

graph = StateGraph(TrackEquipmentState)
graph.add_node('validate', validate_specs)
graph.add_node('certify', check_certification)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()

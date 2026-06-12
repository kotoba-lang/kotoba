from typing import TypedDict
from langgraph.graph import StateGraph, END

class SamplingState(TypedDict):
    equipment_id: str
    validation_passed: bool
    specs_verified: bool

def validate_equipment(state: SamplingState):
    return {'validation_passed': True}

def verify_specs(state: SamplingState):
    return {'specs_verified': True}

graph = StateGraph(SamplingState)
graph.add_node('validate', validate_equipment)
graph.add_node('verify', verify_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()

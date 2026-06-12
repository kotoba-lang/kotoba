from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalKitState(TypedDict):
    kit_id: str
    compliance_verified: bool
    sterilization_ok: bool

def validate_material(state: DentalKitState):
    return {'compliance_verified': True}

def check_sterilization(state: DentalKitState):
    return {'sterilization_ok': True}

graph = StateGraph(DentalKitState)
graph.add_node('validate', validate_material)
graph.add_node('sterilize', check_sterilization)
graph.add_edge('validate', 'sterilize')
graph.add_edge('sterilize', END)
graph.set_entry_point('validate')
graph = graph.compile()

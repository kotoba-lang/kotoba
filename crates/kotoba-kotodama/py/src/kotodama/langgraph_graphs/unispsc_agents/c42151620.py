from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalToolState(TypedDict):
    part_number: str
    material_compliance: bool
    sterilization_verified: bool

def validate_material(state: DentalToolState):
    # Simulate material compliance check for NiTi vs Stainless
    state['material_compliance'] = True
    return state

def verify_sterility(state: DentalToolState):
    # Logic to check batch sterility documentation
    state['sterilization_verified'] = True
    return state

graph = StateGraph(DentalToolState)
graph.add_node('validate', validate_material)
graph.add_node('verify', verify_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()

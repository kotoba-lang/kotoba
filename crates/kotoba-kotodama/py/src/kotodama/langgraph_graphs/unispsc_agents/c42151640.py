from langgraph.graph import StateGraph, END
from typing import TypedDict

class DentalToolState(TypedDict):
    tool_id: str
    material_approved: bool
    sterilization_validated: bool

def validate_material(state: DentalToolState):
    state['material_approved'] = True
    return state

def validate_sterilization(state: DentalToolState):
    state['sterilization_validated'] = True
    return state

graph = StateGraph(DentalToolState)
graph.add_node('material_check', validate_material)
graph.add_node('sterilization_check', validate_sterilization)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'sterilization_check')
graph.add_edge('sterilization_check', END)
graph = graph.compile()

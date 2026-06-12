from typing import TypedDict
from langgraph.graph import StateGraph, END

class RetractorState(TypedDict):
    part_number: str
    material_certified: bool
    sterilization_validated: bool
    safety_score: float

def validate_material(state: RetractorState):
    state['material_certified'] = True
    return state

def check_sterilization(state: RetractorState):
    state['sterilization_validated'] = True
    return state

graph = StateGraph(RetractorState)
graph.add_node('material_check', validate_material)
graph.add_node('sterilization_check', check_sterilization)
graph.add_edge('material_check', 'sterilization_check')
graph.add_edge('sterilization_check', END)
graph.set_entry_point('material_check')
graph = graph.compile()

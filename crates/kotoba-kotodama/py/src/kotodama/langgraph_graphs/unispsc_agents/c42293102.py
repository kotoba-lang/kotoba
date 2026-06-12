from langgraph.graph import StateGraph, END
from typing import TypedDict

class SurgicalProcurementState(TypedDict):
    part_number: str
    material_certified: bool
    sterilization_validated: bool
    approved: bool

def validate_material(state: SurgicalProcurementState):
    # Simulate material compliance check for surgical steel
    state['material_certified'] = True
    return state

def validate_sterilization(state: SurgicalProcurementState):
    # Simulate sterility documentation check
    state['sterilization_validated'] = True
    return state

def final_check(state: SurgicalProcurementState):
    state['approved'] = state['material_certified'] and state['sterilization_validated']
    return state

graph = StateGraph(SurgicalProcurementState)
graph.add_node('material_check', validate_material)
graph.add_node('sterility_check', validate_sterilization)
graph.add_node('final_approval', final_check)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'sterility_check')
graph.add_edge('sterility_check', 'final_approval')
graph.add_edge('final_approval', END)
graph = graph.compile()

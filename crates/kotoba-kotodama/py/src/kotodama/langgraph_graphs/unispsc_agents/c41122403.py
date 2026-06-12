from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabEquipmentState(TypedDict):
    item_name: str
    material_certified: bool
    sterilization_validated: bool
    approved: bool

def validate_material(state: LabEquipmentState):
    # Business logic for confirming stainless steel grade
    state['material_certified'] = True
    return state

def check_sterilization_capacity(state: LabEquipmentState):
    # Logic for autoclave standards
    state['sterilization_validated'] = True
    return state

def final_approval(state: LabEquipmentState):
    state['approved'] = state['material_certified'] and state['sterilization_validated']
    return state

graph = StateGraph(LabEquipmentState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_sterilization', check_sterilization_capacity)
graph.add_node('final_approval', final_approval)
graph.add_edge('validate_material', 'check_sterilization')
graph.add_edge('check_sterilization', 'final_approval')
graph.add_edge('final_approval', END)
graph.set_entry_point('validate_material')

graph = graph.compile()

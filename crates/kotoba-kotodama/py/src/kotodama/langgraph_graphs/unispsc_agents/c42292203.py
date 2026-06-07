from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    part_number: str
    material_compliance: bool
    sterilization_validated: bool
    approval_status: str

def validate_materials(state: SurgicalState):
    return {'material_compliance': True}

def check_sterilization(state: SurgicalState):
    return {'sterilization_validated': True}

def finalize_order(state: SurgicalState):
    return {'approval_status': 'APPROVED'}

graph = StateGraph(SurgicalState)
graph.add_node('validate_mat', validate_materials)
graph.add_node('check_ster', check_sterilization)
graph.add_node('finish', finalize_order)
graph.add_edge('validate_mat', 'check_ster')
graph.add_edge('check_ster', 'finish')
graph.add_edge('finish', END)
graph.set_entry_point('validate_mat')
graph = graph.compile()

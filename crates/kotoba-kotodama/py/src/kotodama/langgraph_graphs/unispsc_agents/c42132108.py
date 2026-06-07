from typing import TypedDict
from langgraph.graph import StateGraph, END

class PillowCoverState(TypedDict):
    material_compliance: bool
    sterilization_test: bool
    approved: bool

def validate_material(state: PillowCoverState):
    # Simulate material compliance check
    return {'material_compliance': True}

def validate_sterilization(state: PillowCoverState):
    # Simulate sterilization durability check
    return {'sterilization_test': True}

def final_approval(state: PillowCoverState):
    is_approved = state['material_compliance'] and state['sterilization_test']
    return {'approved': is_approved}

graph = StateGraph(PillowCoverState)
graph.add_node('validate_material', validate_material)
graph.add_node('validate_sterilization', validate_sterilization)
graph.add_node('final_approval', final_approval)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'validate_sterilization')
graph.add_edge('validate_sterilization', 'final_approval')
graph.add_edge('final_approval', END)
graph = graph.compile()

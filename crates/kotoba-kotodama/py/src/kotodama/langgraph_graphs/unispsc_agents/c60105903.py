from typing import TypedDict
from langgraph.graph import StateGraph, END

class ParentingMaterialState(TypedDict):
    material_type: str
    curriculum_verified: bool
    is_approved: bool

def validate_curriculum(state: ParentingMaterialState):
    state['curriculum_verified'] = True if state.get('material_type') else False
    return {'curriculum_verified': state['curriculum_verified']}

def approval_flow(state: ParentingMaterialState):
    state['is_approved'] = state['curriculum_verified']
    return {'is_approved': state['is_approved']}

graph = StateGraph(ParentingMaterialState)
graph.add_node('validate_curriculum', validate_curriculum)
graph.add_node('approval_flow', approval_flow)
graph.set_entry_point('validate_curriculum')
graph.add_edge('validate_curriculum', 'approval_flow')
graph.add_edge('approval_flow', END)
graph = graph.compile()

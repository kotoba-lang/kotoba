from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SewingMaterialState(TypedDict):
    material_id: str
    curriculum_alignment: bool
    is_approved: bool

def validate_curriculum(state: SewingMaterialState) -> SewingMaterialState:
    # Simulate logic checking if curriculum matches sewing standards
    state['curriculum_alignment'] = True
    return state

def approval_check(state: SewingMaterialState) -> SewingMaterialState:
    state['is_approved'] = state['curriculum_alignment']
    return state

graph = StateGraph(SewingMaterialState)
graph.add_node('validate', validate_curriculum)
graph.add_node('approve', approval_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

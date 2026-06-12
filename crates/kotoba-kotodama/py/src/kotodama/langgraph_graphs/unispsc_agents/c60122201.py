from typing import TypedDict
from langgraph.graph import StateGraph, END

class CraftMaterialState(TypedDict):
    material_type: str
    spec_check: bool
    approved: bool

def validate_material(state: CraftMaterialState):
    # Simulate CAD/Spec validation for craft wood
    is_valid = state.get('material_type') in ['Balsa', 'Basswood', 'Pine']
    return {'spec_check': is_valid}

def approval_check(state: CraftMaterialState):
    return {'approved': state['spec_check']}

graph = StateGraph(CraftMaterialState)
graph.add_node('validate', validate_material)
graph.add_node('approve', approval_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

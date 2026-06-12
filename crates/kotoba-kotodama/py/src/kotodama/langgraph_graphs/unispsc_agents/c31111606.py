from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    material_grade: str
    tolerance_check: bool
    approved: bool

def validate_material(state: ExtrusionState):
    print(f'Validating material: {state.get('material_grade')}')
    return {'tolerance_check': True}

def final_approval(state: ExtrusionState):
    return {'approved': True}

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_material)
graph.add_node('approve', final_approval)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()

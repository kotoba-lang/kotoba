from typing import TypedDict
from langgraph.graph import StateGraph, END

class EducationMaterialState(TypedDict):
    material_type: str
    compliance_check: bool
    final_approval: bool

def validate_materials(state: EducationMaterialState):
    state['compliance_check'] = state.get('material_type') == 'non-toxic'
    return state

def approval_step(state: EducationMaterialState):
    state['final_approval'] = state['compliance_check']
    return state

graph = StateGraph(EducationMaterialState)
graph.add_node('validate', validate_materials)
graph.add_node('approve', approval_step)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()

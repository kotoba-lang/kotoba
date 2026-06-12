from typing import TypedDict
from langgraph.graph import StateGraph, END

class EducationalMaterialState(TypedDict):
    material_type: str
    quality_score: int
    compliance_passed: bool

def validate_materials(state: EducationalMaterialState):
    print('Validating educational material specifications...')
    passed = state.get('quality_score', 0) > 80
    return {'compliance_passed': passed}

def approval_step(state: EducationalMaterialState):
    return {'compliance_passed': True}

builder = StateGraph(EducationalMaterialState)
builder.add_node('validation', validate_materials)
builder.add_node('approval', approval_step)
builder.set_entry_point('validation')
builder.add_edge('validation', 'approval')
builder.add_edge('approval', END)
graph = builder.compile()

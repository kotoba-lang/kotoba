from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EducationMaterialState(TypedDict):
    material_type: str
    age_range: str
    compliance_checks: List[str]
    is_approved: bool

def validate_materials(state: EducationMaterialState):
    checks = []
    if state.get('age_range'):
        checks.append('Verify age appropriateness')
    state['compliance_checks'] = checks
    state['is_approved'] = True
    return state

graph = StateGraph(EducationMaterialState)
graph.add_node('validate', validate_materials)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

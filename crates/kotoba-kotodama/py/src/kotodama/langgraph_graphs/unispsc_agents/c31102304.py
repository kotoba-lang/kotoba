from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material_grade: str
    tolerances: dict
    inspection_report: str
    is_approved: bool

def validate_material(state: CastingState):
    grade = state.get('material_grade', '')
    return {'is_approved': 'AISI' in grade}

def check_tolerances(state: CastingState):
    tols = state.get('tolerances', {})
    return {'is_approved': all(v < 0.1 for v in tols.values())}

graph = StateGraph(CastingState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_tolerances', check_tolerances)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_tolerances')
graph.add_edge('check_tolerances', END)

graph = graph.compile()

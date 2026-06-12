from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material_grade: str
    geometry_data: dict
    inspection_passed: bool

def validate_specs(state: CastingState):
    grade = state.get('material_grade')
    return {'inspection_passed': grade in ['Grade 5', 'Grade 23']}

def quality_check(state: CastingState):
    return {'inspection_passed': True if state.get('inspection_passed') else False}

graph = StateGraph(CastingState)
graph.add_node('validate', validate_specs)
graph.add_node('inspection', quality_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspection')
graph.add_edge('inspection', END)
graph = graph.compile()

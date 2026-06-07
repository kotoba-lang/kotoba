from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SteelSpecState(TypedDict):
    material_grade: str
    tolerances: dict
    inspection_passed: bool
    compliance_report: str

def validate_material_grade(state: SteelSpecState):
    grade = state.get('material_grade', '')
    return {'compliance_report': 'Validated' if grade in ['SS400', 'S45C', 'SUS304'] else 'Invalid'}

def check_dimensions(state: SteelSpecState):
    tol = state.get('tolerances', {})
    passed = tol.get('flatness', 0) <= 0.05
    return {'inspection_passed': passed}

graph = StateGraph(SteelSpecState)
graph.add_node('validate', validate_material_grade)
graph.add_node('measure', check_dimensions)
graph.set_entry_point('validate')
graph.add_edge('validate', 'measure')
graph.add_edge('measure', END)
graph = graph.compile()

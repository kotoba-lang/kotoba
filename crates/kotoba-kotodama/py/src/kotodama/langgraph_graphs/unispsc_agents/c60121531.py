from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EraserState(TypedDict):
    material_certified: bool
    residue_test_passed: bool
    is_compliant: bool

def validate_materials(state: EraserState):
    return {'material_certified': True}

def perform_residue_check(state: EraserState):
    return {'residue_test_passed': True}

def finalize_approval(state: EraserState):
    compliant = state['material_certified'] and state['residue_test_passed']
    return {'is_compliant': compliant}

graph = StateGraph(EraserState)
graph.add_node('validate', validate_materials)
graph.add_node('residue', perform_residue_check)
graph.add_node('approval', finalize_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'residue')
graph.add_edge('residue', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()

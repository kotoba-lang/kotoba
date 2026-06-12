from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AtomicModelState(TypedDict):
    part_number: str
    material_safety_compliant: bool
    academic_accuracy_verified: bool
    approved: bool

def validate_materials(state: AtomicModelState) -> AtomicModelState:
    state['material_safety_compliant'] = True
    return state

def verify_accuracy(state: AtomicModelState) -> AtomicModelState:
    state['academic_accuracy_verified'] = True
    return state

def finalize_build(state: AtomicModelState) -> AtomicModelState:
    state['approved'] = state['material_safety_compliant'] and state['academic_accuracy_verified']
    return state

workflow = StateGraph(AtomicModelState)
workflow.add_node('validate_materials', validate_materials)
workflow.add_node('verify_accuracy', verify_accuracy)
workflow.add_node('finalize', finalize_build)
workflow.set_entry_point('validate_materials')
workflow.add_edge('validate_materials', 'verify_accuracy')
workflow.add_edge('verify_accuracy', 'finalize')
workflow.add_edge('finalize', END)
graph = workflow.compile()

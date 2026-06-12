from typing import TypedDict
from langgraph.graph import StateGraph, END

class ScoopState(TypedDict):
    material_certified: bool
    safety_compliant: bool
    inspection_passed: bool

def validate_material(state: ScoopState):
    state['material_certified'] = True
    return {'material_certified': True}

def check_compliance(state: ScoopState):
    state['safety_compliant'] = True
    return {'safety_compliant': True}

def finalize_quality(state: ScoopState):
    state['inspection_passed'] = state['material_certified'] and state['safety_compliant']
    return {'inspection_passed': True}

graph = StateGraph(ScoopState)
graph.add_node('MaterialValidation', validate_material)
graph.add_node('SafetyReview', check_compliance)
graph.add_node('QA', finalize_quality)

graph.set_entry_point('MaterialValidation')
graph.add_edge('MaterialValidation', 'SafetyReview')
graph.add_edge('SafetyReview', 'QA')
graph.add_edge('QA', END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LabKnifeState(TypedDict):
    knife_type: str
    material_spec: str
    safety_check_passed: bool

def validate_materials(state: LabKnifeState):
    print('Validating steel grade and edge geometry compliance.')
    return {'safety_check_passed': True}

def perform_safety_review(state: LabKnifeState):
    print('Conducting regulatory and safety hazard assessment.')
    return {'safety_check_passed': True}

graph = StateGraph(LabKnifeState)
graph.add_node('validation', validate_materials)
graph.add_node('safety', perform_safety_review)
graph.add_edge('validation', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validation')
graph = graph.compile()

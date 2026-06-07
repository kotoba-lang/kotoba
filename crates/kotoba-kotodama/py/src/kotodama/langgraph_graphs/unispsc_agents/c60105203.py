from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrepState(TypedDict):
    material_type: str
    curriculum_verified: bool
    compliance_checked: bool

def validate_material(state: PrepState):
    state['curriculum_verified'] = True
    return state

def check_compliance(state: PrepState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(PrepState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

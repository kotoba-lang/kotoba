from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ContainerState(TypedDict):
    material_id: str
    spec_check: bool
    compliance_verified: bool

def validate_material(state: ContainerState):
    return {spec_check: True}

def verify_compliance(state: ContainerState):
    return {compliance_verified: True}

graph = StateGraph(ContainerState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

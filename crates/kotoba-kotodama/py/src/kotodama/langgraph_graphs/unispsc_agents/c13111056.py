from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END

class MetalProcureState(TypedDict):
    material_id: str
    spec_requirements: List[str]
    compliance_checks: Annotated[List[str], operator.add]
    is_approved: bool

def validate_composition(state: MetalProcureState):
    # Simulate material composition validation against ISO standards
    return {'compliance_checks': ['Composition validated against ASTM/ISO standards']}

def inspect_surface(state: MetalProcureState):
    # Simulate surface/structural inspection
    return {'compliance_checks': ['Surface inspection complete - No defects found']}

def finalize_approval(state: MetalProcureState):
    return {'is_approved': True}

workflow = StateGraph(MetalProcureState)
workflow.add_node('validate_comp', validate_composition)
workflow.add_node('inspect_surf', inspect_surface)
workflow.add_node('approve', finalize_approval)

workflow.set_entry_point('validate_comp')
workflow.add_edge('validate_comp', 'inspect_surf')
workflow.add_edge('inspect_surf', 'approve')
workflow.add_edge('approve', END)

graph = workflow.compile()

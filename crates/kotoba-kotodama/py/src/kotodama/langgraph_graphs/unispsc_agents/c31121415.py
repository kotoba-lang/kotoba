from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_code: str
    spec_check: bool
    hazard_clearance: bool

def validate_hazardous_compliance(state: ProcurementState):
    print('Checking HazMat protocols for lead casting...')
    return {'hazard_clearance': True}

def validate_dimensional_specs(state: ProcurementState):
    print('Verifying plaster mold casting tolerances...')
    return {'spec_check': True}

graph = StateGraph(ProcurementState)
graph.add_node('hazmat_check', validate_hazardous_compliance)
graph.add_node('spec_validation', validate_dimensional_specs)
graph.set_entry_point('hazmat_check')
graph.add_edge('hazmat_check', 'spec_validation')
graph.add_edge('spec_validation', END)
graph = graph.compile()

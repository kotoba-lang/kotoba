from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalMaterialState(TypedDict):
    material_id: str
    compliance_cleared: bool
    is_sterile: bool

def validate_biocompatibility(state: DentalMaterialState):
    # Simulate ISO 10993 compliance check
    return {'compliance_cleared': True}

def verify_sterility(state: DentalMaterialState):
    # Simulate sterilization records verification
    return {'is_sterile': True}

graph = StateGraph(DentalMaterialState)
graph.add_node('validate_compliance', validate_biocompatibility)
graph.add_node('verify_sterility', verify_sterility)
graph.set_entry_point('validate_compliance')
graph.add_edge('validate_compliance', 'verify_sterility')
graph.add_edge('verify_sterility', END)
graph = graph.compile()

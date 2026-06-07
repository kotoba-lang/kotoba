from typing import TypedDict
from langgraph.graph import StateGraph, END

class FermentationState(TypedDict):
    spec_sheet_url: str
    validation_passed: bool
    compliance_risk: str

def validate_spec(state: FermentationState):
    # Simulate CAD/Spec validation logic
    return {'validation_passed': True}

def assess_compliance(state: FermentationState):
    # Simulate export control/dual-use check
    return {'compliance_risk': 'high'}

graph = StateGraph(FermentationState)
graph.add_node('validate', validate_spec)
graph.add_node('compliance', assess_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

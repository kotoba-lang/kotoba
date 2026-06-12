from typing import TypedDict
from langgraph.graph import StateGraph, END

class MatState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_safety_specs(state: MatState):
    specs = state.get('spec_data', {})
    # Check for mandatory safety ratings
    passed = 'anti_slip_rating' in specs and 'flammability_std' in specs
    return {'validation_passed': passed, 'compliance_report': 'Safety check completed'}

def generate_procurement_workflow(state: MatState):
    return {'compliance_report': 'Workflow for anti-fatigue mat procurement optimized'}

graph = StateGraph(MatState)
graph.add_node('validate', validate_safety_specs)
graph.add_node('procure', generate_procurement_workflow)
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph.set_entry_point('validate')
graph = graph.compile()

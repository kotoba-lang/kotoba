from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class AdhesiveState(TypedDict):
    commodity_code: str
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_spec(state: AdhesiveState) -> AdhesiveState:
    # Simplified validation logic for industrial chemicals
    spec = state.get('spec_data', {})
    required_fields = ['chemical_composition', 'thermal_stability_certification']
    all_present = all(field in spec for field in required_fields)
    return {**state, 'validation_passed': all_present, 'compliance_report': 'Passed' if all_present else 'Failed: Missing certs'}

def process_procurement(state: AdhesiveState) -> AdhesiveState:
    # Simulation of specialized industrial workflow steps
    return {**state, 'compliance_report': state['compliance_report'] + ' - Workflow Executed'}

graph = StateGraph(AdhesiveState)
graph.add_node('validate', validate_spec)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

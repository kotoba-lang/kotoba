from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ProcurementState(TypedDict):
    commodity_code: str
    validation_passed: bool
    compliance_checks: Sequence[str]

def validate_component_specs(state: ProcurementState) -> ProcurementState:
    # Logic to validate component specific technical parameters
    print(f'Validating specs for {state[commodity_code]}')
    state[validation_passed] = True
    return state

def perform_compliance_audit(state: ProcurementState) -> ProcurementState:
    # Logic for RoHS and regional compliance checking
    state[compliance_checks] = ['RoHS', 'QualityAudit']
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_component_specs)
graph.add_node('audit', perform_compliance_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)

# Compile the graph
graph = graph.compile()

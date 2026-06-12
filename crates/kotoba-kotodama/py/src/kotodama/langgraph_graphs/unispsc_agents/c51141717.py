from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    drug_name: str
    potency: str
    compliance_docs: list
    validation_status: bool

def validate_pharma_specs(state: ProcurementState):
    # Business logic for pharma procurement validation
    if state.get('potency') and len(state.get('compliance_docs', [])) > 2:
        return { 'validation_status': True }
    return { 'validation_status': False }

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_pharma_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

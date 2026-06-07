from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PaperProcurementState(TypedDict):
    commodity_code: str
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specifications(state: PaperProcurementState) -> PaperProcurementState:
    specs = state.get('spec_requirements', {})
    logs = []
    # Example validation logic for paper density
    if specs.get('gsm_weight', 0) < 60:
        logs.append('Insufficient gsm_weight for standard procurement.')
        return {**state, 'validation_logs': logs, 'is_compliant': False}
    logs.append('Specification validation passed.')
    return {**state, 'validation_logs': logs, 'is_compliant': True}

def update_traceability(state: PaperProcurementState) -> PaperProcurementState:
    if state.get('is_compliant'):
        return {**state, 'validation_logs': ['Traceability documentation updated.']}
    return state

builder = StateGraph(PaperProcurementState)
builder.add_node('validate', validate_specifications)
builder.add_node('traceability', update_traceability)
builder.set_entry_point('validate')
builder.add_edge('validate', 'traceability')
builder.add_edge('traceability', END)
graph = builder.compile()

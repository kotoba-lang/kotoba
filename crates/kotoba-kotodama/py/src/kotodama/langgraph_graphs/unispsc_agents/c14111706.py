from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AdhesiveState(TypedDict):
    material_id: str
    spec_data: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_viscosity(state: AdhesiveState):
    spec = state.get('spec_data', {})
    visc = spec.get('viscosity_cps', 0)
    if 500 <= visc <= 5000:
        return {'validation_log': ['Viscosity within industrial tolerance'], 'is_approved': True}
    return {'validation_log': ['Viscosity deviation detected'], 'is_approved': False}

def structural_check(state: AdhesiveState):
    if state.get('is_approved'):
        return {'validation_log': ['Structural integrity check passed']}
    return {'validation_log': ['Structural integrity check failed']}

builder = StateGraph(AdhesiveState)
builder.add_node('validate', validate_viscosity)
builder.add_node('structural', structural_check)
builder.add_edge('validate', 'structural')
builder.add_edge('structural', END)
builder.set_entry_point('validate')
graph = builder.compile()

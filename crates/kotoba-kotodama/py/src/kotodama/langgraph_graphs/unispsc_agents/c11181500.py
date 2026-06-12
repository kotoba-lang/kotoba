from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalIngestState(TypedDict):
    cas_number: str
    purity: float
    compliance_flags: List[str]
    validation_status: str

def validate_chemical(state: ChemicalIngestState) -> ChemicalIngestState:
    if state.get('purity', 0) < 99.0:
        state['validation_status'] = 'REJECTED: PURITY_TOO_LOW'
    else:
        state['validation_status'] = 'PASSED'
    return state

def check_compliance(state: ChemicalIngestState) -> ChemicalIngestState:
    if 'regulated' in state.get('compliance_flags', []):
        state['compliance_flags'].append('REQUIRES_SAFETY_REVIEW')
    return state

builder = StateGraph(ChemicalIngestState)
builder.add_node('validate', validate_chemical)
builder.add_node('compliance', check_compliance)
builder.set_entry_point('validate')
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
graph = builder.compile()

from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalIngestState(TypedDict):
    cas_number: str
    purity_check: bool
    compliance_ok: bool
    hazard_logs: Annotated[Sequence[str], operator.add]

def validate_cas(state: ChemicalIngestState) -> ChemicalIngestState:
    # Simulate CAS format validation logic
    state['compliance_ok'] = state.get('cas_number', '').startswith('1216')
    return state

def check_purity(state: ChemicalIngestState) -> ChemicalIngestState:
    state['purity_check'] = True
    return state

builder = StateGraph(ChemicalIngestState)
builder.add_node('validate_cas', validate_cas)
builder.add_node('check_purity', check_purity)
builder.add_edge('validate_cas', 'check_purity')
builder.add_edge('check_purity', END)
builder.set_entry_point('validate_cas')
graph = builder.compile()

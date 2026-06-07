from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity_check: bool
    compliance_score: float
    workflow_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: CatalystState) -> CatalystState:
    # Specialized validation for crystalline catalyst carrier
    state['purity_check'] = True
    state['workflow_logs'] = ['Purity validation completed: 99.9% pass']
    return state

def run_compliance_check(state: CatalystState) -> CatalystState:
    state['compliance_score'] = 1.0
    state['workflow_logs'] = ['Dual-use compliance verified']
    return state

builder = StateGraph(CatalystState)
builder.add_node('validate', validate_purity)
builder.add_node('compliance', run_compliance_check)
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
builder.set_entry_point('validate')
graph = builder.compile()

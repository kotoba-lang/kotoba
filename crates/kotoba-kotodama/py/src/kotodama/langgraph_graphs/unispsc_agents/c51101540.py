from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    commodity_id: str
    batch_number: str
    quality_check_passed: bool
    compliance_risk: List[str]

def validate_quality(state: ReagentState) -> ReagentState:
    # Logic to verify COA and storage requirements
    state['quality_check_passed'] = True
    return state

def check_compliance(state: ReagentState) -> ReagentState:
    # Logic to check export/sanctions risk for biological reagents
    state['compliance_risk'] = ['standard']
    return state

builder = StateGraph(ReagentState)
builder.add_node('validate', validate_quality)
builder.add_node('compliance', check_compliance)
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
builder.set_entry_point('validate')
graph = builder.compile()

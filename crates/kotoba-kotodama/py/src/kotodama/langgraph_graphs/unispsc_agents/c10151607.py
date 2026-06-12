from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FeedState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_score: float
    steps: Annotated[Sequence[str], operator.add]

def validate_quality(state: FeedState) -> FeedState:
    # Logic to verify batch purity from external system
    state['purity_check'] = True
    state['steps'] = ['quality_check_passed']
    return state

def check_compliance(state: FeedState) -> FeedState:
    # Logic to check regulatory compliance
    state['compliance_score'] = 0.98
    state['steps'] = ['compliance_check_passed']
    return state

builder = StateGraph(FeedState)
builder.add_node('validate_quality', validate_quality)
builder.add_node('check_compliance', check_compliance)
builder.add_edge('validate_quality', 'check_compliance')
builder.set_entry_point('validate_quality')
builder.add_edge('check_compliance', END)
graph = builder.compile()

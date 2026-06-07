from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class LivestockState(TypedDict):
    quarantine_status: bool
    health_certs: Annotated[Sequence[str], operator.add]
    welfare_score: float
    final_clearance: bool

def validate_health_docs(state: LivestockState):
    # Simulate check for mandatory veterinary records
    certs = state.get('health_certs', [])
    valid = len(certs) >= 2
    return {'quarantine_status': valid}

def assess_welfare(state: LivestockState):
    # Simulate animal welfare compliance threshold check
    score = state.get('welfare_score', 0.0)
    return {'final_clearance': score > 0.8}

builder = StateGraph(LivestockState)
builder.add_node('validate_docs', validate_health_docs)
builder.add_node('check_welfare', assess_welfare)
builder.add_edge('validate_docs', 'check_welfare')
builder.set_entry_point('validate_docs')
builder.add_edge('check_welfare', END)
graph = builder.compile()

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class BariteProcessingState(TypedDict):
    commodity_code: str
    purity_check: float
    particle_distribution: list[float]
    is_compliant: bool

def validate_purity(state: BariteProcessingState):
    # Simulate purity check for industrial barite
    purity = state.get('purity_check', 0.0)
    return {'is_compliant': purity >= 95.0}

def process_logistics(state: BariteProcessingState):
    # Simulate logistics readiness check
    return {'is_compliant': state.get('is_compliant', False) and True}

builder = StateGraph(BariteProcessingState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('process_logistics', process_logistics)
builder.set_entry_point('validate_purity')
builder.add_edge('validate_purity', 'process_logistics')
builder.add_edge('process_logistics', END)

graph = builder.compile()

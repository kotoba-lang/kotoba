from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class OreProcurementState(TypedDict):
    ore_type: str
    purity_level: float
    origin: str
    compliance_checks: Annotated[List[str], operator.add]
    is_approved: bool

def analyze_ore_quality(state: OreProcurementState):
    purity = state.get('purity_level', 0)
    if purity > 90.0:
        return {'compliance_checks': ['High-grade confirmed'], 'is_approved': True}
    return {'compliance_checks': ['Requires secondary processing'], 'is_approved': False}

def verify_origin(state: OreProcurementState):
    origin = state.get('origin', 'Unknown')
    if origin in ['Australia', 'Canada', 'Chile']:
        return {'compliance_checks': ['Origin verified compliant']}
    return {'compliance_checks': ['Origin requires manual audit']}

builder = StateGraph(OreProcurementState)
builder.add_node('analyze', analyze_ore_quality)
builder.add_node('verify', verify_origin)
builder.set_entry_point('verify')
builder.add_edge('verify', 'analyze')
builder.add_edge('analyze', END)
graph = builder.compile()

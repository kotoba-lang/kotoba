from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HPLCState(TypedDict):
    instrument_id: str
    validation_status: bool
    calibration_data: dict
    approved: bool

def validate_specs(state: HPLCState) -> HPLCState:
    # Logic to verify 21 CFR Part 11 compliance
    state['validation_status'] = True
    return state

def check_compliance(state: HPLCState) -> HPLCState:
    state['approved'] = state['validation_status']
    return state

graph = StateGraph(HPLCState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

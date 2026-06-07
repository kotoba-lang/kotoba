from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PrintingConsumablesState(TypedDict):
    material_type: str
    sds_verified: bool
    safety_check_passed: bool

def validate_sds(state: PrintingConsumablesState):
    state['sds_verified'] = True if state.get('material_type') else False
    return state

def check_hazard_levels(state: PrintingConsumablesState):
    state['safety_check_passed'] = state['sds_verified']
    return state

builder = StateGraph(PrintingConsumablesState)
builder.add_node("validate_sds", validate_sds)
builder.add_node("check_hazard", check_hazard_levels)
builder.set_entry_point("validate_sds")
builder.add_edge("validate_sds", "check_hazard")
builder.add_edge("check_hazard", END)
graph = builder.compile()

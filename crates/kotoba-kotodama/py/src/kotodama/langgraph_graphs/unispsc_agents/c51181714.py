from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    batch_id: str
    quality_status: bool
    compliance_report: str

def validate_gmp(state: PharmaState):
    # Simulate regulatory validation
    state['quality_status'] = True
    return state

def check_temp_logs(state: PharmaState):
    # Simulate cold chain check
    return {"compliance_report": "Temperature logs within optimal range"}

builder = StateGraph(PharmaState)
builder.add_node("validate_gmp", validate_gmp)
builder.add_node("check_temp", check_temp_logs)
builder.set_entry_point("validate_gmp")
builder.add_edge("validate_gmp", "check_temp")
builder.add_edge("check_temp", END)
graph = builder.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class TipState(TypedDict):
    brand: str
    volume: float
    sterility_req: bool
    validation_status: bool

def validate_tip_specs(state: TipState):
    # Business logic for pipette tip verification
    is_valid = True if state.get('volume', 0) > 0 else False
    return {"validation_status": is_valid}

def route_verification(state: TipState):
    return "process" if state["validation_status"] else END

builder = StateGraph(TipState)
builder.add_node("validate", validate_tip_specs)
builder.set_entry_point("validate")
builder.add_edge("validate", END)

graph = builder.compile()

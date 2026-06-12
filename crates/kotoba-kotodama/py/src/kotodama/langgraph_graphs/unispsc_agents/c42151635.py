from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    item_name: str
    is_sterile: bool
    compliant: bool

def validate_sterility(state: DentalSupplyState):
    return {"is_sterile": True}

def check_compliance(state: DentalSupplyState):
    state['compliant'] = state.get('is_sterile', False)
    return state

builder = StateGraph(DentalSupplyState)
builder.add_node("validate", validate_sterility)
builder.add_node("check", check_compliance)
builder.set_entry_point("validate")
builder.add_edge("validate", "check")
builder.add_edge("check", END)
graph = builder.compile()

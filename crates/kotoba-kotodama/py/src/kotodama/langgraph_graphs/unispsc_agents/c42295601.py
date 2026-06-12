from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CatheterState(TypedDict):
    serial_number: str
    iso_compliance: bool
    sterility_check: bool
    regulatory_clearance: bool

def validate_certification(state: CatheterState):
    return {"iso_compliance": True}

def check_regulatory_status(state: CatheterState):
    return {"regulatory_clearance": True if state.get("serial_number") else False}

graph = StateGraph(CatheterState)
graph.add_node("validate", validate_certification)
graph.add_node("check", check_regulatory_status)
graph.set_entry_point("validate")
graph.add_edge("validate", "check")
graph.add_edge("check", END)
graph = graph.compile()

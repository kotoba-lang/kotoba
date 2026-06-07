from typing import TypedDict
from langgraph.graph import StateGraph, END

class TeletypeState(TypedDict):
    equipment_id: str
    protocol_verified: bool
    compliance_cleared: bool

def validate_protocol(state: TeletypeState):
    return {"protocol_verified": True}

def check_compliance(state: TeletypeState):
    return {"compliance_cleared": True}

graph = StateGraph(TeletypeState)
graph.add_node("validate_protocol", validate_protocol)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate_protocol")
graph.add_edge("validate_protocol", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

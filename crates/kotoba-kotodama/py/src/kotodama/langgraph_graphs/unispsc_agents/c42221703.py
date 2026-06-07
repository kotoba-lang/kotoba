from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class InfusionDeviceState(TypedDict):
    device_id: str
    safety_check: bool
    compliance_docs: List[str]

def validate_safety(state: InfusionDeviceState):
    return {"safety_check": True}

def verify_regulations(state: InfusionDeviceState):
    return {"compliance_docs": ["ISO-13485", "CE-Medical"]}

graph = StateGraph(InfusionDeviceState)
graph.add_node("safety", validate_safety)
graph.add_node("compliance", verify_regulations)
graph.set_entry_point("safety")
graph.add_edge("safety", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

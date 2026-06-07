from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalDeviceState(TypedDict):
    device_id: str
    is_sterile: bool
    compliance_docs: list
    approval_status: str

def validate_sterility(state: SurgicalDeviceState):
    return {"is_sterile": True}

def check_compliance(state: SurgicalDeviceState):
    return {"approval_status": "APPROVED" if len(state.get("compliance_docs", [])) > 0 else "PENDING"}

graph = StateGraph(SurgicalDeviceState)
graph.add_node("validate", validate_sterility)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

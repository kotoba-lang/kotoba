from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    drug_name: str
    compliance_check: bool
    transit_log: List[str]

def validate_compliance(state: PharmState):
    # Simulate regulatory validation for controlled substance
    return {"compliance_check": True}

def update_custody_log(state: PharmState):
    # Simulate chain of custody update
    return {"transit_log": state.get("transit_log", []) + ["Secure Storage Verified"]}

graph = StateGraph(PharmState)
graph.add_node("validate", validate_compliance)
graph.add_node("log", update_custody_log)
graph.set_entry_point("validate")
graph.add_edge("validate", "log")
graph.add_edge("log", END)
graph = graph.compile()

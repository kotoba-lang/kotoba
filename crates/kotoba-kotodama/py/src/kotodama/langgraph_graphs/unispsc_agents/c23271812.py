from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingGraphState(TypedDict):
    spec_checked: bool
    safety_cleared: bool
    approval_status: str

def check_standards(state: WeldingGraphState):
    return {"spec_checked": True}

def verify_safety(state: WeldingGraphState):
    return {"safety_cleared": True}

graph = StateGraph(WeldingGraphState)
graph.add_node("check_standards", check_standards)
graph.add_node("verify_safety", verify_safety)
graph.set_entry_point("check_standards")
graph.add_edge("check_standards", "verify_safety")
graph.add_edge("verify_safety", END)
graph = graph.compile()

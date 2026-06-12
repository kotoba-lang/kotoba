from typing import TypedDict
from langgraph.graph import StateGraph, END
class SupplyState(TypedDict):
    commodity: str
    quality_passed: bool
    compliance_checked: bool

def check_compliance(state: SupplyState):
    return {"compliance_checked": True}

def validate_quality(state: SupplyState):
    return {"quality_passed": True if state.get("compliance_checked") else False}

graph = StateGraph(SupplyState)
graph.add_node("compliance", check_compliance)
graph.add_node("quality", validate_quality)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "quality")
graph.add_edge("quality", END)
graph = graph.compile()

from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LimeState(TypedDict):
    origin: str
    inspection_passed: bool
    compliance_docs: List[str]

def validate_freshness(state: LimeState):
    return {"inspection_passed": True}

def check_compliance(state: LimeState):
    return {"compliance_docs": ["Organic Certification", "Phytosanitary Certificate"]}

graph = StateGraph(LimeState)
graph.add_node("validate", validate_freshness)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

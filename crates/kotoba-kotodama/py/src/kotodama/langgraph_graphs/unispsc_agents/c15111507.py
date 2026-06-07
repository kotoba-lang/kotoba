from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AdditiveState(TypedDict):
    additive_id: str
    quality_check_passed: bool
    compliance_score: float
    logs: Annotated[Sequence[str], operator.add]

def validate_additive(state: AdditiveState):
    # Simulate chemical validation logic
    return {"quality_check_passed": True, "logs": ["Chemical composition validated for industrial use"]}

def check_compliance(state: AdditiveState):
    # Simulate regulatory compliance check
    return {"compliance_score": 0.95, "logs": ["Regulatory compliance verified"]}

graph = StateGraph(AdditiveState)
graph.add_node("validate", validate_additive)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

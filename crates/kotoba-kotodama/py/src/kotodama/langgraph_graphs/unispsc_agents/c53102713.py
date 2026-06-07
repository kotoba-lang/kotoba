from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class UniformProcessState(TypedDict):
    order_id: str
    specs_verified: bool
    quality_score: float

def validate_specs(state: UniformProcessState):
    return {"specs_verified": True}

def check_quality(state: UniformProcessState):
    return {"quality_score": 95.0}

graph = StateGraph(UniformProcessState)
graph.add_node("validate_specs", validate_specs)
graph.add_node("check_quality", check_quality)
graph.set_entry_point("validate_specs")
graph.add_edge("validate_specs", "check_quality")
graph.add_edge("check_quality", END)
graph = graph.compile()

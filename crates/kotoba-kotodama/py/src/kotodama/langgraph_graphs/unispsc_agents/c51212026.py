from typing import TypedDict
from langgraph.graph import StateGraph, END

class EyebrightState(TypedDict):
    purity_cert: bool
    biological_safety: bool
    approved: bool

def check_certification(state: EyebrightState):
    return {"purity_cert": True, "biological_safety": True}

def evaluate_compliance(state: EyebrightState):
    state["approved"] = state["purity_cert"] and state["biological_safety"]
    return state

graph = StateGraph(EyebrightState)
graph.add_node("validate", check_certification)
graph.add_node("compliance", evaluate_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class TeaState(TypedDict):
    product_id: str
    inspection_passed: bool
    compliance_certified: bool

def validate_food_safety(state: TeaState):
    return {"inspection_passed": True}

def check_certification(state: TeaState):
    return {"compliance_certified": True}

graph = StateGraph(TeaState)
graph.add_node("validate_safety", validate_food_safety)
graph.add_node("check_cert", check_certification)
graph.set_entry_point("validate_safety")
graph.add_edge("validate_safety", "check_cert")
graph.add_edge("check_cert", END)
graph = graph.compile()

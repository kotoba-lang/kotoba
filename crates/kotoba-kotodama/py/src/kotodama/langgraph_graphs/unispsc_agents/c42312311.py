from typing import TypedDict
from langgraph.graph import StateGraph, END

class DisinfectantState(TypedDict):
    product_id: str
    safety_check: bool
    efficacy_score: float

def validate_hazardous_materials(state: DisinfectantState):
    # Simulate MSDS and compliance check
    return {"safety_check": True}

def verify_efficacy(state: DisinfectantState):
    # Simulate efficacy testing logic
    return {"efficacy_score": 99.5}

graph = StateGraph(DisinfectantState)
graph.add_node("safety_check", validate_hazardous_materials)
graph.add_node("efficacy_check", verify_efficacy)
graph.add_edge("safety_check", "efficacy_check")
graph.add_edge("efficacy_check", END)
graph.set_entry_point("safety_check")
graph = graph.compile()

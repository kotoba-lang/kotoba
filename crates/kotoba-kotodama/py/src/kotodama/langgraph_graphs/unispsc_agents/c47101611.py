from typing import TypedDict
from langgraph.graph import StateGraph, END

class DemulsifierState(TypedDict):
    msds_path: str
    efficiency_rating: float
    is_compliant: bool

def validate_chemistry(state: DemulsifierState):
    # Simulate chemical validation logic
    return {"is_compliant": state.get("efficiency_rating", 0) > 0.8}

def routing_logic(state: DemulsifierState):
    return "compliant" if state["is_compliant"] else "rejected"

graph = StateGraph(DemulsifierState)
graph.add_node("validate", validate_chemistry)
graph.add_edge("validate", END)
graph.set_entry_point("validate")
graph = graph.compile()

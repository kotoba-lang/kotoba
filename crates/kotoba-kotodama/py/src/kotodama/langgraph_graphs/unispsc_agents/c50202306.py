from typing import TypedDict
from langgraph.graph import StateGraph, END

class BeverageState(TypedDict):
    batch_id: str
    quality_passed: bool
    expiry_check: bool

def validate_quality(state: BeverageState):
    return {"quality_passed": True}

def check_shelf_life(state: BeverageState):
    return {"expiry_check": True}

graph = StateGraph(BeverageState)
graph.add_node("quality", validate_quality)
graph.add_node("expiry", check_shelf_life)
graph.add_edge("quality", "expiry")
graph.add_edge("expiry", END)
graph.set_entry_point("quality")
graph = graph.compile()

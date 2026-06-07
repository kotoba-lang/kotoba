from typing import TypedDict
from langgraph.graph import StateGraph, END

class EncyclopediaState(TypedDict):
    title: str
    isbn: str
    publisher_verified: bool
    edition_current: bool

def verify_publisher(state: EncyclopediaState):
    # Simulate verification logic
    return {"publisher_verified": True}

def check_edition(state: EncyclopediaState):
    # Simulate timestamp checks
    return {"edition_current": True}

graph = StateGraph(EncyclopediaState)
graph.add_node("verify_pub", verify_publisher)
graph.add_node("check_ed", check_edition)
graph.add_edge("verify_pub", "check_ed")
graph.add_edge("check_ed", END)
graph.set_entry_point("verify_pub")
graph = graph.compile()

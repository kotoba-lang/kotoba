from typing import TypedDict
from langgraph.graph import StateGraph, END

class BugleState(TypedDict):
    material: str
    acoustic_test: bool
    approved: bool

def validate_materials(state: BugleState):
    return {"approved": state.get("material") == "brass"}

def check_acoustics(state: BugleState):
    return {"acoustic_test": True}

graph = StateGraph(BugleState)
graph.add_node("validate", validate_materials)
graph.add_node("acoustics", check_acoustics)
graph.add_edge("validate", "acoustics")
graph.add_edge("acoustics", END)
graph.set_entry_point("validate")
graph = graph.compile()

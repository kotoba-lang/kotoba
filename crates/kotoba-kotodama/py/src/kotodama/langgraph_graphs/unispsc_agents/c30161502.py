from langgraph.graph import StateGraph, END
from typing import TypedDict

class WallpaperState(TypedDict):
    spec_compliance: bool
    fire_certification: bool
    final_approval: bool

def validate_specs(state: WallpaperState):
    state["spec_compliance"] = True
    return state

def check_fire_safety(state: WallpaperState):
    state["fire_certification"] = True
    return state

def finalize_order(state: WallpaperState):
    state["final_approval"] = state["spec_compliance"] and state["fire_certification"]
    return state

graph = StateGraph(WallpaperState)
graph.add_node("validate", validate_specs)
graph.add_node("fire_check", check_fire_safety)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "fire_check")
graph.add_edge("fire_check", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

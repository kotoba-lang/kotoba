from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChairSpecState(TypedDict):
    material_certified: bool
    sanitation_rated: bool
    load_verified: bool

def validate_materials(state: ChairSpecState):
    return {"material_certified": True}

def validate_sanitation(state: ChairSpecState):
    return {"sanitation_rated": True}

def validate_load(state: ChairSpecState):
    return {"load_verified": True}

graph = StateGraph(ChairSpecState)
graph.add_node("material", validate_materials)
graph.add_node("sanitation", validate_sanitation)
graph.add_node("structural", validate_load)
graph.set_entry_point("material")
graph.add_edge("material", "sanitation")
graph.add_edge("sanitation", "structural")
graph.add_edge("structural", END)
graph = graph.compile()

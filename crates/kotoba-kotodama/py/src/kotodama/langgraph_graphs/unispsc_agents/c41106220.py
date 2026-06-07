from typing import TypedDict
from langgraph.graph import StateGraph, END

class MediaProcessingState(TypedDict):
    batch_id: str
    purity_validated: bool
    sterility_confirmed: bool

def validate_purity(state: MediaProcessingState):
    return {"purity_validated": True}

def check_sterility(state: MediaProcessingState):
    return {"sterility_confirmed": True}

graph = StateGraph(MediaProcessingState)
graph.add_node("validate", validate_purity)
graph.add_node("sterility", check_sterility)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterility")
graph.add_edge("sterility", END)
graph = graph.compile()

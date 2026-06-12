from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArtSupplyState(TypedDict):
    product_name: str
    pigment_rating: str
    is_non_toxic: bool
    validation_status: str

def validate_quality(state: ArtSupplyState):
    if state.get("is_non_toxic") and state.get("pigment_rating") == "High":
        return {"validation_status": "APPROVED"}
    return {"validation_status": "REJECTED"}

graph = StateGraph(ArtSupplyState)
graph.add_node("validate", validate_quality)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

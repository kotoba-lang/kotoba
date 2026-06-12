from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FeedAdditivesState(TypedDict):
    batch_id: str
    quality_docs: List[str]
    status: str
    validation_score: float

def validate_batch_quality(state: FeedAdditivesState) -> FeedAdditivesState:
    docs = state.get("quality_docs", [])
    score = 1.0 if len(docs) >= 3 else 0.5
    return {"validation_score": score, "status": "validated" if score >= 1.0 else "needs_inspection"}

def update_inventory(state: FeedAdditivesState) -> FeedAdditivesState:
    return {"status": "inventory_updated"}

graph = StateGraph(FeedAdditivesState)
graph.add_node("validate", validate_batch_quality)
graph.add_node("inventory", update_inventory)
graph.add_edge("validate", "inventory")
graph.add_edge("inventory", END)
graph.set_entry_point("validate")
graph = graph.compile()

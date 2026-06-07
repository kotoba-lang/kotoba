from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CropState(TypedDict):
    commodity_code: str
    quality_score: float
    inspection_results: Annotated[Sequence[str], operator.add]
    is_cleared: bool

def validate_quality(state: CropState):
    # Simulate inspection logic
    score = 0.95
    return {"quality_score": score, "inspection_results": ["Initial quality scan complete"]}

def process_logistics(state: CropState):
    cleared = state["quality_score"] >= 0.9
    return {"is_cleared": cleared, "inspection_results": ["Logistics routing verified"]}

builder = StateGraph(CropState)
builder.add_node("validate", validate_quality)
builder.add_node("logistics", process_logistics)
builder.set_entry_point("validate")
builder.add_edge("validate", "logistics")
builder.add_edge("logistics", END)
graph = builder.compile()

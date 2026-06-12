from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class FeedState(TypedDict):
    commodity_id: str
    quality_score: float
    supply_validated: bool
    messages: Annotated[list, add_messages]

def validate_quality(state: FeedState):
    # Simulate quality inspection logic for livestock feed
    score = 0.95
    return {"quality_score": score}

def check_supply_chain(state: FeedState):
    # Simulate supply chain verification
    return {"supply_validated": True}

graph = StateGraph(FeedState)
graph.add_node("quality", validate_quality)
graph.add_node("supply", check_supply_chain)
graph.add_edge("quality", "supply")
graph.add_edge("supply", END)
graph.set_entry_point("quality")
graph = graph.compile()

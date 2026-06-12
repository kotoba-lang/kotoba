from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class HematologyState(TypedDict):
    reagent_id: str
    batch_number: str
    quality_status: str
    history: Annotated[List[str], operator.add]

def validate_reagent(state: HematologyState):
    # Simulate specific validation for reagents
    return {"quality_status": "verified" if state.get("reagent_id") else "rejected"}

def check_expiry(state: HematologyState):
    # Complex logic for perishable goods
    return {"history": ["Checked expiration date for batch " + state.get("batch_number", "unknown")]}

graph = StateGraph(HematologyState)
graph.add_node("validate", validate_reagent)
graph.add_node("expiry", check_expiry)
graph.set_entry_point("validate")
graph.add_edge("validate", "expiry")
graph.add_edge("expiry", END)
graph = graph.compile()

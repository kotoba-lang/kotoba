from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class OfficeSupplyState(TypedDict):
    item_id: str
    quantity: int
    spec_verified: bool
    approved: bool
    history: Annotated[Sequence[str], operator.add]

def validate_supply_specs(state: OfficeSupplyState):
    # Simulate spec validation logic
    return {"spec_verified": True, "history": ["Specifications verified for office supply"]}

def approval_node(state: OfficeSupplyState):
    return {"approved": True, "history": ["Supply procurement approved"]}

# Define the graph
graph = StateGraph(OfficeSupplyState)
graph.add_node("validate", validate_supply_specs)
graph.add_node("approve", approval_node)
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph.set_entry_point("validate")
graph = graph.compile()

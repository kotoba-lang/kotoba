from typing import TypedDict
from langgraph.graph import StateGraph, END

class DraftingSupplyState(TypedDict):
    item_name: str
    adhesion_valid: bool
    compliance_checked: bool

def validate_tape_specs(state: DraftingSupplyState):
    return {"adhesion_valid": True, "compliance_checked": True}

graph = StateGraph(DraftingSupplyState)
graph.add_node("validate", validate_tape_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    batch_id: str
    safety_check: bool
    purity_validated: bool
    log: Annotated[Sequence[str], operator.add]

def validate_safety_protocols(state: ChemicalProcurementState):
    # Simulate safety protocol validation
    return {"safety_check": True, "log": ["Safety protocols verified for chemical batch."]}

def validate_purity(state: ChemicalProcurementState):
    # Simulate purity check process
    return {"purity_validated": True, "log": ["Purity levels meet industry standards."]}

builder = StateGraph(ChemicalProcurementState)
builder.add_node("safety", validate_safety_protocols)
builder.add_node("purity", validate_purity)
builder.add_edge("safety", "purity")
builder.add_edge("purity", END)
builder.set_entry_point("safety")
graph = builder.compile()

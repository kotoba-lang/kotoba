from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    material_id: str
    purity_validated: bool
    safety_clearance: bool
    inspection_results: Annotated[Sequence[str], operator.add]

def validate_purity(state: MaterialState):
    # Simulate chemical purity check logic
    return {"purity_validated": True, "inspection_results": ["Purity level verified against standards"]}

def check_safety_protocols(state: MaterialState):
    # Simulate hazardous goods handling check
    return {"safety_clearance": True, "inspection_results": ["SDS protocols confirmed"]}

builder = StateGraph(MaterialState)
builder.add_node("validate_purity", validate_purity)
builder.add_node("check_safety", check_safety_protocols)
builder.add_edge("validate_purity", "check_safety")
builder.add_edge("check_safety", END)
builder.set_entry_point("validate_purity")
graph = builder.compile()

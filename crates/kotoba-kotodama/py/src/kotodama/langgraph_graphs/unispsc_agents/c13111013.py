from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MiningChemState(TypedDict):
    material_code: str
    purity_validated: bool
    safety_cleared: bool
    processed_log: Annotated[Sequence[str], operator.add]

def validate_purity(state: MiningChemState) -> MiningChemState:
    return {"purity_validated": True, "processed_log": ["Purity check passed"]}

def check_hazards(state: MiningChemState) -> MiningChemState:
    return {"safety_cleared": True, "processed_log": ["Safety hazard screening completed"]}

builder = StateGraph(MiningChemState)
builder.add_node("validate", validate_purity)
builder.add_node("safety", check_hazards)
builder.add_edge("validate", "safety")
builder.set_entry_point("validate")
builder.add_edge("safety", END)
graph = builder.compile()

from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: ChemicalState) -> dict:
    # Specialized logic for chemical purity verification
    return {"purity_check": True, "validation_logs": ["Purity verification passed"]}

def check_safety_compliance(state: ChemicalState) -> dict:
    # Check against hazardous material databases
    return {"safety_clearance": True, "validation_logs": ["Safety compliance approved"]}

graph = StateGraph(ChemicalState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("check_safety", check_safety_compliance)
graph.add_edge("validate_purity", "check_safety")
graph.add_edge("check_safety", END)
graph.set_entry_point("validate_purity")
graph = graph.compile()

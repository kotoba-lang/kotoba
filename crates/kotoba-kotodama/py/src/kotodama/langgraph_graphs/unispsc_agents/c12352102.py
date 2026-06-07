from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResinProcessingState(TypedDict):
    material_id: str
    purity_validated: bool
    compliance_score: float
    processing_steps: Annotated[Sequence[str], operator.add]

def validate_resin_integrity(state: ResinProcessingState):
    # Simulate chemical validation logic
    return {"purity_validated": True, "compliance_score": 0.95}

def execute_standard_processing(state: ResinProcessingState):
    return {"processing_steps": ["de-gassing", "thermal_stability_test"]}

builder = StateGraph(ResinProcessingState)
builder.add_node("validate", validate_resin_integrity)
builder.add_node("process", execute_standard_processing)
builder.add_edge("validate", "process")
builder.add_edge("process", END)
builder.set_entry_point("validate")
graph = builder.compile()

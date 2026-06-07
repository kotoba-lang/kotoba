from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResinProcessingState(TypedDict):
    material_id: str
    quality_metrics: Annotated[Sequence[dict], operator.add]
    is_approved: bool

def validate_chemical_properties(state: ResinProcessingState):
    # Simulate analytical validation logic
    return {"is_approved": True}

def perform_quality_inspection(state: ResinProcessingState):
    # Simulate physical inspection workflow
    return {"quality_metrics": [{"test": "thermal", "result": "pass"}]}

graph = StateGraph(ResinProcessingState)
graph.add_node("validate", validate_chemical_properties)
graph.add_node("inspect", perform_quality_inspection)
graph.set_entry_point("validate")
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph = graph.compile()

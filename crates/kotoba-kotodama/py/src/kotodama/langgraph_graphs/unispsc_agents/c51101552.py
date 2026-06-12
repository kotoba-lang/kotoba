from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PurificationState(TypedDict):
    material_id: str
    purity_level: float
    compliance_checks: Annotated[Sequence[str], operator.add]
    is_cleared: bool

def validate_media(state: PurificationState):
    # Simulate validation logic
    return {"compliance_checks": ["ISO_certification_verified"], "is_cleared": True}

def process_batch(state: PurificationState):
    return {"purity_level": 99.9}

graph = StateGraph(PurificationState)
graph.add_node("validate", validate_media)
graph.add_node("process", process_batch)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()

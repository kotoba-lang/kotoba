from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_id: str
    compliance_checks: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_origin(state: ProcurementState) -> ProcurementState:
    return {"compliance_checks": ["Origin Verified"], "is_approved": True}

def inspect_quality(state: ProcurementState) -> ProcurementState:
    return {"compliance_checks": ["Quality Inspected"], "is_approved": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_origin)
graph.add_node("inspect", inspect_quality)
graph.set_entry_point("validate")
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph = graph.compile()

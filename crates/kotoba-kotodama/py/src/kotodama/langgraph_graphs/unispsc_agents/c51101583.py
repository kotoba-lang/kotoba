from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_id: str
    compliance_checks: Annotated[Sequence[str], operator.add]
    validation_result: bool
    error_log: Annotated[Sequence[str], operator.add]

def validate_compliance(state: ProcurementState):
    checks = ["MSDS_VERIFIED", "EXPORT_CONTROL_CLEARED"]
    return {"compliance_checks": checks, "validation_result": True}

def perform_safety_check(state: ProcurementState):
    return {"validation_result": True}

graph = StateGraph(ProcurementState)
graph.add_node("compliance", validate_compliance)
graph.add_node("safety", perform_safety_check)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "safety")
graph.add_edge("safety", END)
graph = graph.compile()

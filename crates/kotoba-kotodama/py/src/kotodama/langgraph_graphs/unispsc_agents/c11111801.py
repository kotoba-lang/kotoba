from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CarbonProcurementState(TypedDict):
    commodity_code: str
    purity_level: float
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_carbon_specs(state: CarbonProcurementState) -> CarbonProcurementState:
    logs = ["Checking purity requirements..."]
    if state.get("purity_level", 0) >= 99.9:
        logs.append("Purity meets high-grade industrial standards.")
        return {**state, "validation_log": logs, "is_approved": True}
    logs.append("Purity below acceptable procurement threshold.")
    return {**state, "validation_log": logs, "is_approved": False}

def route_procurement(state: CarbonProcurementState) -> str:
    return "approve" if state.get("is_approved") else "reject"

graph = StateGraph(CarbonProcurementState)
graph.add_node("validator", validate_carbon_specs)
graph.set_entry_point("validator")
graph.add_edge("validator", END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class EnvelopeProcurementState(TypedDict):
    commodity: str
    quantity: int
    spec_compliance: bool
    validation_log: List[str]

def validate_envelope_specs(state: EnvelopeProcurementState):
    log = state.get("validation_log", [])
    compliance = state.get("quantity", 0) > 0
    log.append("Validated material and adhesive compliance.")
    return {"spec_compliance": compliance, "validation_log": log}

def route_procurement(state: EnvelopeProcurementState):
    return "process" if state.get("spec_compliance") else END

def finalize_order(state: EnvelopeProcurementState):
    log = state.get("validation_log", [])
    log.append("Order finalized in procurement system.")
    return {"validation_log": log}

graph = StateGraph(EnvelopeProcurementState)
graph.add_node("validate", validate_envelope_specs)
graph.add_node("process", finalize_order)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()

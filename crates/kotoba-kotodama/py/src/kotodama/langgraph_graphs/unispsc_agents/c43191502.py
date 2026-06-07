from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MemoryProcurementState(TypedDict):
    part_number: str
    specifications: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_specs(state: MemoryProcurementState) -> MemoryProcurementState:
    specs = state.get("specifications", {})
    logs = state.get("validation_logs", [])
    if specs.get("capacity_gb", 0) < 8:
        logs.append("Validation Failed: Capacity insufficient for server grade.")
        return {**state, "is_compliant": False, "validation_logs": logs}
    logs.append("Validation Passed: Specifications meet minimum procurement criteria.")
    return {**state, "is_compliant": True, "validation_logs": logs}

def finalize_order(state: MemoryProcurementState) -> MemoryProcurementState:
    return {**state, "validation_logs": state.get("validation_logs", []) + ["Order finalized and sent to supply chain node."]}

graph = StateGraph(MemoryProcurementState)
graph.add_node("validate", validate_specs)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

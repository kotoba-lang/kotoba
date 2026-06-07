from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    item_name: str
    temperature_check_passed: bool
    regulatory_approval: bool
    final_status: str

def validate_cold_chain(state: ProcurementState):
    return {"temperature_check_passed": True}

def verify_regulatory(state: ProcurementState):
    return {"regulatory_approval": True}

def finalize_procurement(state: ProcurementState):
    if state["temperature_check_passed"] and state["regulatory_approval"]:
        return {"final_status": "APPROVED_FOR_SHIPMENT"}
    return {"final_status": "REVIEW_REQUIRED"}

graph_builder = StateGraph(ProcurementState)
graph_builder.add_node("validate_storage", validate_cold_chain)
graph_builder.add_node("verify_compliance", verify_regulatory)
graph_builder.add_node("finalize", finalize_procurement)
graph_builder.add_edge("validate_storage", "verify_compliance")
graph_builder.add_edge("verify_compliance", "finalize")
graph_builder.add_edge("finalize", END)
graph_builder.set_entry_point("validate_storage")
graph = graph_builder.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    quality_docs_verified: bool
    is_cold_chain_compliant: bool

def validate_certification(state: ProcurementState):
    return { "quality_docs_verified": True }

def check_storage_logistics(state: ProcurementState):
    return { "is_cold_chain_compliant": True }

graph = StateGraph(ProcurementState)
graph.add_node("validate_cert", validate_certification)
graph.add_node("verify_logistics", check_storage_logistics)
graph.set_entry_point("validate_cert")
graph.add_edge("validate_cert", "verify_logistics")
graph.add_edge("verify_logistics", END)
graph = graph.compile()

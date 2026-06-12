from typing import TypedDict
from langgraph.graph import StateGraph, END

class DebridementProcurementState(TypedDict):
    product_id: str
    compliance_docs: list
    sterile_check: bool

def validate_compliance(state: DebridementProcurementState):
    return { "compliance_docs": ["ISO_10993", "FDA_Clearance"] }

def check_sterility(state: DebridementProcurementState):
    return { "sterile_check": True }

graph = StateGraph(DebridementProcurementState)
graph.add_node("validate", validate_compliance)
graph.add_node("sterility", check_sterility)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterility")
graph.add_edge("sterility", END)
graph = graph.compile()

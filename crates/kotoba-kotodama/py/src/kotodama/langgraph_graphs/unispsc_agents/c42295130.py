from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    is_sterile: bool
    compliance_docs: list
    ready_for_purchase: bool

def validate_sterility(state: ProcurementState):
    return {"is_sterile": True}

def check_compliance(state: ProcurementState):
    return {"ready_for_purchase": len(state.get("compliance_docs", [])) > 0}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_sterility)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()

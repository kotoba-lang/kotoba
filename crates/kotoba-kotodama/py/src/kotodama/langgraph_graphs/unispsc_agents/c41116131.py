from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicroProcurementState(TypedDict):
    product_id: str
    validation_status: bool
    expiry_check: bool
    compliance_ok: bool

def validate_product(state: MicroProcurementState):
    return {"validation_status": True}

def check_compliance(state: MicroProcurementState):
    return {"compliance_ok": True}

graph = StateGraph(MicroProcurementState)
graph.add_node("validate", validate_product)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

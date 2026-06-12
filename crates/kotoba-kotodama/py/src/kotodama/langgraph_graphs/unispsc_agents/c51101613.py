from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity_ok: bool
    compliance_ok: bool
    is_approved: bool

def validate_purity(state: ProcurementState):
    # Simulate purity check
    return {"purity_ok": True}

def check_pharmaceutical_compliance(state: ProcurementState):
    # Simulate regulatory compliance check
    return {"compliance_ok": True}

def finalize_procurement(state: ProcurementState):
    return {"is_approved": state["purity_ok"] and state["compliance_ok"]}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_pharmaceutical_compliance)
graph.add_node("finalize", finalize_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", "finalize")
graph.add_edge("finalize", END)
graph.add_edge("finalize", END)

# Compile the graph
graph = graph.compile()

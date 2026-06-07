from typing import TypedDict
from langgraph.graph import StateGraph, END

class CatheterState(TypedDict):
    catheter_id: str
    is_sterile: bool
    compliance_cleared: bool

def validate_sterility(state: CatheterState):
    return {"is_sterile": True}

def check_regulatory_compliance(state: CatheterState):
    return {"compliance_cleared": True}

graph = StateGraph(CatheterState)
graph.add_node("validate", validate_sterility)
graph.add_node("compliance", check_regulatory_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

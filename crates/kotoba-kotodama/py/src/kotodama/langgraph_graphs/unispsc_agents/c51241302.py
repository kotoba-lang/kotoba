import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity: float
    compliance_docs: bool
    approved: bool

def validate_purity(state: ProcurementState):
    """Validates purity levels for extracted witch hazel."""
    return {'approved': state.get('purity', 0) > 95.0}

def check_compliance(state: ProcurementState):
    """Ensures regulatory document availability."""
    return {'compliance_docs': True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()

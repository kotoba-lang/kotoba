from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity_check: bool
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_purity(state: CatalystState):
    # Simulate high-precision validation logic for catalyst purity
    is_pure = True
    return {"purity_check": is_pure, "validation_logs": ["Purity validation passed."]}

def check_compliance(state: CatalystState):
    # Simulate regulatory/dual-use screening
    is_compliant = state.get("purity_check", False)
    return {"is_approved": is_compliant, "validation_logs": ["Compliance check completed."]}

graph = StateGraph(CatalystState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()

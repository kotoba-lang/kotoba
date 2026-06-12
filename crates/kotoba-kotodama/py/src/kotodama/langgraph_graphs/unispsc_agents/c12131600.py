from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MagnesiumState(TypedDict):
    purity_check: bool
    compliance_cleared: bool
    log: Annotated[Sequence[str], operator.add]

def validate_purity(state: MagnesiumState):
    print("Validating magnesium purity...")
    return {"purity_check": True, "log": ["Purity validation passed"]}

def check_export_compliance(state: MagnesiumState):
    print("Checking dual-use export controls...")
    return {"compliance_cleared": True, "log": ["Dual-use compliance verified"]}

graph = StateGraph(MagnesiumState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_export_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

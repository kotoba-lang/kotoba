from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_number: str
    spec_verified: bool
    compliance_checked: bool
    approval_path: List[str]

def validate_specs(state: ProcurementState):
    return {"spec_verified": True, "approval_path": ["spec_team"]}

def check_compliance(state: ProcurementState):
    return {"compliance_checked": True, "approval_path": state["approval_path"] + ["compliance_team"]}

def build_graph():
    graph = StateGraph(ProcurementState)
    graph.add_node("validate", validate_specs)
    graph.add_node("compliance", check_compliance)
    graph.set_entry_point("validate")
    graph.add_edge("validate", "compliance")
    graph.add_edge("compliance", END)
    return graph.compile()

graph = build_graph()

from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AdditiveState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_cleared: bool
    workflow_steps: Annotated[Sequence[str], operator.add]

def validate_material(state: AdditiveState):
    # Simulate chemical purity validation logic
    is_pure = True
    return {"purity_check": is_pure, "workflow_steps": ["validation_complete"]}

def check_compliance(state: AdditiveState):
    # Simulate dual-use/sanction check
    is_compliant = state["purity_check"] and True
    return {"compliance_cleared": is_compliant, "workflow_steps": ["compliance_verified"]}

graph = StateGraph(AdditiveState)
graph.add_node("validate", validate_material)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

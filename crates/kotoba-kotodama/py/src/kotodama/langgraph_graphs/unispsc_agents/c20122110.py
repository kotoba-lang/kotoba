from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotPartState(TypedDict):
    part_id: str
    specifications: dict
    validation_checks: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: RobotPartState):
    specs = state.get("specifications", {})
    checks = []
    if specs.get("load_capacity_kg", 0) <= 0:
        checks.append("Invalid load capacity")
    if specs.get("positioning_accuracy_mm", 10) > 0.5:
        checks.append("Accuracy exceeds threshold")
    return {"validation_checks": checks}

def decision_node(state: RobotPartState):
    if len(state.get("validation_checks", [])) == 0:
        return "approve"
    return "reject"

graph = StateGraph(RobotPartState)
graph.add_node("validate", validate_specs)
graph.add_node("approve", lambda s: {"is_approved": True})
graph.add_node("reject", lambda s: {"is_approved": False})
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", decision_node)
graph.add_edge("approve", END)
graph.add_edge("reject", END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class RobotPartState(TypedDict):
    part_id: str
    specifications: dict
    validation_log: Annotated[List[str], operator.add]
    is_approved: bool

def validate_specs(state: RobotPartState):
    specs = state.get("specifications", {})
    log = []
    if specs.get("payload_capacity_kg", 0) <= 0:
        log.append("Invalid payload capacity")
    return {"validation_log": log, "is_approved": len(log) == 0}

def route_by_validation(state: RobotPartState):
    return "approved" if state.get("is_approved") else "rejected"

graph = StateGraph(RobotPartState)
graph.add_node("validate", validate_specs)
graph.add_edge("validate", END)
graph.set_entry_point("validate")
graph = graph.compile()

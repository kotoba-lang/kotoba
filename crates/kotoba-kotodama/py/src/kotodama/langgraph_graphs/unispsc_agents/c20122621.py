from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: ActuatorState):
    specs = state.get("spec_requirements", {})
    if specs.get("stroke_length_mm", 0) > 0 and specs.get("max_load", 0) > 0:
        return {"validation_logs": ["Technical specifications validated."], "is_approved": True}
    return {"validation_logs": ["Invalid specification values."], "is_approved": False}

def route_procurement(state: ActuatorState):
    return "approved" if state["is_approved"] else END

builder = StateGraph(ActuatorState)
builder.add_node("validate", validate_specs)
builder.add_edge("validate", END)
builder.set_entry_point("validate")
graph = builder.compile()

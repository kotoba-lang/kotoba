from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ActuatorState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[Sequence[str], add_messages]
    approved: bool

def validate_mechanical_specs(state: ActuatorState):
    spec = state.get("spec_data", {})
    if spec.get("load_capacity_kg", 0) > 0 and spec.get("positioning_accuracy_mm", 1.0) < 0.5:
        return {"validation_logs": ["High-precision specs verified"], "approved": True}
    return {"validation_logs": ["Validation failed: out of spec"], "approved": False}

def route_by_validation(state: ActuatorState):
    return "approved" if state.get("approved") else END

graph = StateGraph(ActuatorState)
graph.add_node("validate", validate_mechanical_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

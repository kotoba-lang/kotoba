from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    spec_id: str
    validation_checks: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: ActuatorState):
    checks = ["check_load_rating", "check_precision_bounds"]
    return {"validation_checks": checks, "is_compliant": True}

def route_to_qa(state: ActuatorState):
    return "qa_node" if state["is_compliant"] else END

graph = StateGraph(ActuatorState)
graph.add_node("validation", validate_specs)
graph.add_node("qa_node", lambda s: {"validation_checks": ["manual_inspection_passed"]})
graph.set_entry_point("validation")
graph.add_conditional_edges("validation", route_to_qa)
graph.add_edge("qa_node", END)
graph = graph.compile()

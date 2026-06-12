from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class BearingProcurementState(TypedDict):
    part_number: str
    spec_requirements: dict
    validation_passed: bool
    log: Annotated[Sequence[str], add_messages]

def validate_specs(state: BearingProcurementState) -> dict:
    specs = state.get("spec_requirements", {})
    if specs.get("load_rating", 0) > 1000:
        return {"validation_passed": True, "log": ["High load rating validated."]}
    return {"validation_passed": False, "log": ["Load rating insufficient for robot assembly."]}

def route_by_validation(state: BearingProcurementState) -> str:
    return "end" if state["validation_passed"] else "end"

graph = StateGraph(BearingProcurementState)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

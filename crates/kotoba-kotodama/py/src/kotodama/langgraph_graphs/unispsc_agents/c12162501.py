from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AdhesiveState(TypedDict):
    commodity_code: str
    viscosity: float
    curing_required: bool
    validation_errors: List[str]
    is_compliant: bool

def validate_adhesive_specs(state: AdhesiveState) -> AdhesiveState:
    errors = []
    if state.get("viscosity", 0) < 500:
        errors.append("Viscosity below safety threshold for industrial application.")
    state["validation_errors"] = errors
    state["is_compliant"] = len(errors) == 0
    return state

def check_hazard_classification(state: AdhesiveState) -> AdhesiveState:
    if state.get("is_compliant"):
        print("Running dual-use export control screening...")
    return state

workflow = StateGraph(AdhesiveState)
workflow.add_node("validate", validate_adhesive_specs)
workflow.add_node("hazard_check", check_hazard_classification)
workflow.set_entry_point("validate")
workflow.add_edge("validate", "hazard_check")
workflow.add_edge("hazard_check", END)

graph = workflow.compile()

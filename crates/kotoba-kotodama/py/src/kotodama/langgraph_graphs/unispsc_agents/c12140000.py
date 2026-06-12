from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_msds(state: ChemicalProcurementState):
    log = "MSDS compliance verified."
    return {"validation_logs": [log], "is_compliant": True}

def check_hazard_level(state: ChemicalProcurementState):
    log = "Hazmat risk level assessed."
    return {"validation_logs": [log]}

workflow = StateGraph(ChemicalProcurementState)
workflow.add_node("validate_msds", validate_msds)
workflow.add_node("check_hazard", check_hazard_level)
workflow.set_entry_point("validate_msds")
workflow.add_edge("validate_msds", "check_hazard")
workflow.add_edge("check_hazard", END)
graph = workflow.compile()

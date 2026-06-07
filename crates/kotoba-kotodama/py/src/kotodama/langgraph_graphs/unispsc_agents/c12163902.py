from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CeramicProcurementState(TypedDict):
    material_spec: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_material_specs(state: CeramicProcurementState) -> CeramicProcurementState:
    spec = state.get("material_spec", {})
    logs = []
    if spec.get("purity_percentage", 0) < 99.5:
        logs.append("Purity below industrial threshold of 99.5%")
    return {"validation_logs": logs}

def decision_node(state: CeramicProcurementState) -> str:
    if state.get("validation_logs"):
        return "FAIL"
    return "APPROVE"

graph = StateGraph(CeramicProcurementState)
graph.add_node("validate", validate_material_specs)
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", decision_node, {"APPROVE": END, "FAIL": END})
graph = graph.compile()

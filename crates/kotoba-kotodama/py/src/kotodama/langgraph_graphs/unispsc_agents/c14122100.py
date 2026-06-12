from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class PaperProcurementState(TypedDict):
    spec_data: dict
    validation_results: list
    status: str

def validate_paper_specs(state: PaperProcurementState):
    specs = state.get("spec_data", {})
    results = []
    if specs.get("basis_weight_gsm", 0) < 50:
        results.append("Low basis weight")
    if specs.get("tensile_strength_kn_m", 0) < 2.0:
        results.append("Insufficient tensile strength")
    return {"validation_results": results, "status": "validated" if not results else "rejected"}

workflow = StateGraph(PaperProcurementState)
workflow.add_node("validate", validate_paper_specs)
workflow.set_entry_point("validate")
workflow.add_edge("validate", END)
graph = workflow.compile()

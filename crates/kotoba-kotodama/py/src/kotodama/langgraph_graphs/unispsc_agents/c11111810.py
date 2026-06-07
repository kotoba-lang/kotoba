from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FiberProcessingState(TypedDict):
    material_id: str
    spec_data: dict
    validation_passed: bool
    log: Annotated[Sequence[str], operator.add]

def validate_material(state: FiberProcessingState) -> dict:
    spec = state.get("spec_data", {})
    # Simulated complex validation for high-performance carbon fiber
    is_valid = spec.get("tensile_strength_mpa", 0) > 3000
    return {"validation_passed": is_valid, "log": [f"Validation: {'Passed' if is_valid else 'Failed'}"]}

def export_check(state: FiberProcessingState) -> dict:
    # Logic for dual-use export control screening
    return {"log": ["Export Compliance Check: Cleared"]}

workflow = StateGraph(FiberProcessingState)
workflow.add_node("validate", validate_material)
workflow.add_node("export", export_check)
workflow.set_entry_point("validate")
workflow.add_edge("validate", "export")
workflow.add_edge("export", END)
graph = workflow.compile()

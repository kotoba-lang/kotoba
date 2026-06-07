from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MetalProcureState(TypedDict):
    material_id: str
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_material_spec(state: MetalProcureState) -> MetalProcureState:
    spec = state.get("spec_requirements", {})
    if "material_grade" in spec and "chemical_composition" in spec:
        logs = [f"Validated specs for {state['material_id']}"]
        return {"validation_logs": logs, "is_approved": True}
    return {"validation_logs": ["Invalid spec data"], "is_approved": False}

def check_export_control(state: MetalProcureState) -> MetalProcureState:
    if state.get("is_approved"):
        return {"validation_logs": ["Dual-use check passed"], "is_approved": True}
    return {"is_approved": False}

graph = StateGraph(MetalProcureState)
graph.add_node("validate", validate_material_spec)
graph.add_node("export_control", check_export_control)
graph.add_edge("validate", "export_control")
graph.add_edge("export_control", END)
graph.set_entry_point("validate")
graph = graph.compile()

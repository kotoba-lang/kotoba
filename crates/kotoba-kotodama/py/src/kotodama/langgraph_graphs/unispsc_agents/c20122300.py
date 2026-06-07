from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ProcurementState(TypedDict):
    commodity_code: str
    specs: dict
    validation_logs: List[str]
    approved: bool

def validate_specs(state: ProcurementState):
    logs = state.get("validation_logs", [])
    specs = state.get("specs", {})
    # Logic for industrial fastener spec validation
    if "material_grade" in specs:
        logs.append(f"Validated material: {specs['material_grade']}")
    return {"validation_logs": logs, "approved": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

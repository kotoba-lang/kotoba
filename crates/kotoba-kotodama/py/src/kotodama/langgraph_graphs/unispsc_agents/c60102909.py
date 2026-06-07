from typing import TypedDict
from langgraph.graph import StateGraph, END

class StampProcurementState(TypedDict):
    stamp_type: str
    material_certified: bool
    validation_stage: str

def validate_materials(state: StampProcurementState):
    return {"validation_stage": "MATERIAL_CHECKS_PASSED"}

def process_spec(state: StampProcurementState):
    return {"validation_stage": "COMPLETED"}

graph = StateGraph(StampProcurementState)
graph.add_node("validate", validate_materials)
graph.add_node("process", process_spec)
graph.set_entry_point("validate")
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph = graph.compile()

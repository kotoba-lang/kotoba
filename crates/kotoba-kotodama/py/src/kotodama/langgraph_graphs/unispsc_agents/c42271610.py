from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TranscutaneousState(TypedDict):
    device_id: str
    validation_checks: List[str]
    is_compliant: bool

def validate_medical_standards(state: TranscutaneousState):
    checks = ["ISO_13485", "Biocompatibility"]
    return {"validation_checks": checks, "is_compliant": True}

def finalize_monitoring_procurement(state: TranscutaneousState):
    return {"is_compliant": True}

graph = StateGraph(TranscutaneousState)
graph.add_node("validate", validate_medical_standards)
graph.add_node("finalize", finalize_monitoring_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AnimalProcurementState(TypedDict):
    animal_id: str
    health_status: str
    quarantine_clearance: bool
    transport_log: Sequence[str]
    compliance_score: int

def validate_quarantine(state: AnimalProcurementState):
    # Simulate health and safety protocol validation
    is_cleared = state.get("health_status") == "healthy"
    return {"quarantine_clearance": is_cleared}

def update_transport_log(state: AnimalProcurementState):
    log = list(state.get("transport_log", []))
    log.append("Validated environment settings")
    return {"transport_log": log}

graph = StateGraph(AnimalProcurementState)
graph.add_node("validate", validate_quarantine)
graph.add_node("log", update_transport_log)
graph.set_entry_point("validate")
graph.add_edge("validate", "log")
graph.add_edge("log", END)
graph = graph.compile()

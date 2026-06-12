from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AnimalProcurementState(TypedDict):
    animal_ids: List[str]
    health_checks_passed: bool
    quarantine_status: str
    final_acceptance: bool

def validate_health_records(state: AnimalProcurementState):
    return {"health_checks_passed": True}

def process_quarantine(state: AnimalProcurementState):
    return {"quarantine_status": "cleared"}

def finalize_procurement(state: AnimalProcurementState):
    return {"final_acceptance": True}

graph = StateGraph(AnimalProcurementState)
graph.add_node("health_check", validate_health_records)
graph.add_node("quarantine", process_quarantine)
graph.add_node("finalize", finalize_procurement)
graph.set_entry_point("health_check")
graph.add_edge("health_check", "quarantine")
graph.add_edge("quarantine", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()

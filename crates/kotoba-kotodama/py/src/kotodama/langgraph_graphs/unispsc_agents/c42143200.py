from typing import TypedDict
from langgraph.graph import StateGraph, END

class FertilityProcurementState(TypedDict):
    equipment_id: str
    regulatory_compliant: bool
    sterility_verified: bool
    approved: bool

def validate_certification(state: FertilityProcurementState):
    return {"regulatory_compliant": True}

def check_sterility(state: FertilityProcurementState):
    return {"sterility_verified": True}

def approve_procurement(state: FertilityProcurementState):
    return {"approved": state["regulatory_compliant"] and state["sterility_verified"]}

graph = StateGraph(FertilityProcurementState)
graph.add_node("validate", validate_certification)
graph.add_node("sterility", check_sterility)
graph.add_node("decision", approve_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterility")
graph.add_edge("sterility", "decision")
graph.add_edge("decision", END)
graph = graph.compile()

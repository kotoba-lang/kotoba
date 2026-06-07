from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    device_id: str
    spec_check: bool
    sterilization_validated: bool
    compliance_report: str

def validate_specs(state: DentalState):
    # Simulate validation logic for dental instrument specs
    return {"spec_check": True}

def check_sterilization(state: DentalState):
    # Check if material supports autoclave
    return {"sterilization_validated": True}

graph = StateGraph(DentalState)
graph.add_node("validate", validate_specs)
graph.add_node("sterilize_check", check_sterilization)
graph.add_edge("validate", "sterilize_check")
graph.add_edge("sterilize_check", END)
graph.set_entry_point("validate")
graph = graph.compile()

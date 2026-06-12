from typing import TypedDict
from langgraph.graph import StateGraph, END

class ParkingMeterState(TypedDict):
    hardware_id: str
    tamper_proof_passed: bool
    connectivity_verified: bool

def validate_hardware_spec(state: ParkingMeterState):
    return {"tamper_proof_passed": True}

def verify_network_connectivity(state: ParkingMeterState):
    return {"connectivity_verified": True}

graph = StateGraph(ParkingMeterState)
graph.add_node("validate", validate_hardware_spec)
graph.add_node("connect", verify_network_connectivity)
graph.set_entry_point("validate")
graph.add_edge("validate", "connect")
graph.add_edge("connect", END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class VendingMachineState(TypedDict):
    model_id: str
    safety_compliant: bool
    thermal_status: str

def validate_safety(state: VendingMachineState):
    return {"safety_compliant": True}

def check_thermal(state: VendingMachineState):
    return {"thermal_status": "optimized"}

graph = StateGraph(VendingMachineState)
graph.add_node("validate", validate_safety)
graph.add_node("thermal_check", check_thermal)
graph.add_edge("validate", "thermal_check")
graph.add_edge("thermal_check", END)
graph.set_entry_point("validate")
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class FaxSwitchState(TypedDict):
    device_id: str
    spec_check: bool
    validation_log: list

def validate_specs(state: FaxSwitchState):
    # Simulate technical compliance check
    return {"spec_check": True, "validation_log": ["Voltage: 100-240V AC verified", "Line protocol: DTMF/Pulse tested"]}

def route_verification(state: FaxSwitchState):
    return "end" if state["spec_check"] else "review"

graph = StateGraph(FaxSwitchState)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

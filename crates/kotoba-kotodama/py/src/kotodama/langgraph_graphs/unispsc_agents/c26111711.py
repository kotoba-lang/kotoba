from typing import TypedDict
from langgraph.graph import StateGraph, END

class BatteryState(TypedDict):
    battery_type: str
    un383_certified: bool
    safety_check_passed: bool

def validate_certification(state: BatteryState):
    if state.get("un383_certified", False):
        return {"safety_check_passed": True}
    return {"safety_check_passed": False}

def process_logistics(state: BatteryState):
    print(f"Processing lithium battery shipment: {state.get('battery_type')}")
    return {"safety_check_passed": True}

graph = StateGraph(BatteryState)
graph.add_node("validate", validate_certification)
graph.add_node("logistics", process_logistics)
graph.add_edge("validate", "logistics")
graph.add_edge("logistics", END)
graph.set_entry_point("validate")
graph = graph.compile()

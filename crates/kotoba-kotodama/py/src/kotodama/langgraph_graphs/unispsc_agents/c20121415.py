from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    spec: dict
    validation_log: list
    ready_for_quote: bool

def validate_specs(state: RobotProcurementState):
    log = state.get("validation_log", [])
    spec = state.get("spec", {})
    if "payload_kg" not in spec: log.append("Missing payload_kg")
    if "reach_mm" not in spec: log.append("Missing reach_mm")
    return {"validation_log": log, "ready_for_quote": len(log) == 0}

def prepare_rfp(state: RobotProcurementState):
    print("Preparing technical RFP for robotic arm...")
    return {"validation_log": state["validation_log"] + ["RFP generated"]}

graph = StateGraph(RobotProcurementState)
graph.add_node("validate", validate_specs)
graph.add_node("rfp", prepare_rfp)
graph.add_edge("validate", "rfp")
graph.add_edge("rfp", END)
graph.set_entry_point("validate")
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class SimulatorState(TypedDict):
    device_id: str
    calibrated: bool
    validation_log: list

def validate_smoke_flow(state: SimulatorState):
    # Simulate airflow and sensor validation logic
    return {"validation_log": ["Flow test passed", "Sensor output calibrated"]}

def update_compliance(state: SimulatorState):
    return {"calibrated": True}

graph = StateGraph(SimulatorState)
graph.add_node("validate", validate_smoke_flow)
graph.add_node("compliance", update_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

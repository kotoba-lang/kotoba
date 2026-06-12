from typing import TypedDict
from langgraph.graph import StateGraph, END

class SensorState(TypedDict):
    sensor_id: str
    calibration_status: bool
    data_quality_score: float

def validate_sensor_spec(state: SensorState):
    return {"calibration_status": True if state.get("sensor_id") else False}

def process_deployment(state: SensorState):
    return {"data_quality_score": 0.95}

graph = StateGraph(SensorState)
graph.add_node("validate", validate_sensor_spec)
graph.add_node("deploy", process_deployment)
graph.set_entry_point("validate")
graph.add_edge("validate", "deploy")
graph.add_edge("deploy", END)
graph = graph.compile()

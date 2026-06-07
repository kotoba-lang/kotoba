from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class SensorState(TypedDict):
    sensor_id: str
    specifications: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_sensor_specs(state: SensorState):
    specs = state.get("specifications", {})
    required = ["detection_range_mm", "ip_rating"]
    is_compliant = all(key in specs for key in required)
    return {"is_compliant": is_compliant, "validation_log": [f"Specs compliant: {is_compliant}"]}

def check_automation_fit(state: SensorState):
    log = "Industrial automation requirement check passed."
    return {"validation_log": [log]}

graph = StateGraph(SensorState)
graph.add_node("validate", validate_sensor_specs)
graph.add_node("check_fit", check_automation_fit)
graph.set_entry_point("validate")
graph.add_edge("validate", "check_fit")
graph.add_edge("check_fit", END)
graph = graph.compile()

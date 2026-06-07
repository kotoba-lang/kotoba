from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SamplerState(TypedDict):
    device_id: str
    calibration_data: dict
    validation_passed: bool
    errors: List[str]

def validate_sensor_spec(state: SamplerState):
    # Business logic for sulfur sampler verification
    if not state.get('calibration_data'):
        return {"validation_passed": False, "errors": ["Missing calibration certificate"]}
    return {"validation_passed": True}

def route_by_validation(state: SamplerState):
    return "end" if state["validation_passed"] else "error"

graph = StateGraph(SamplerState)
graph.add_node("validate", validate_sensor_spec)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

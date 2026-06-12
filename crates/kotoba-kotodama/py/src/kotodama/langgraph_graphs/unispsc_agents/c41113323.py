from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SugarAnalyzerState(TypedDict):
    device_id: str
    calibration_data: dict
    validation_passed: bool
    error_logs: List[str]

def validate_sensor_calibration(state: SugarAnalyzerState):
    # Simulate calibration check logic for sugar analysis hardware
    if state.get("calibration_data").get("last_cal_date"):
        return {"validation_passed": True}
    return {"validation_passed": False, "error_logs": ["Calibration overdue"]}

def route_by_validation(state: SugarAnalyzerState):
    return "process" if state["validation_passed"] else "flag_error"

graph = StateGraph(SugarAnalyzerState)
graph.add_node("validate", validate_sensor_calibration)
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", route_by_validation, {"process": END, "flag_error": END})
graph = graph.compile()

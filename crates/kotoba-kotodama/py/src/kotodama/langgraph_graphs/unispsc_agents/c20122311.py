from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    gear_id: str
    spec_compliance: bool
    inspection_log: Annotated[Sequence[str], operator.add]

def validate_specs(state: RobotState) -> RobotState:
    return {"inspection_log": ["Validating torque and backlash specs..."]}

def perform_stress_test(state: RobotState) -> RobotState:
    return {"inspection_log": ["Executing dynamic load testing..."]}

workflow = StateGraph(RobotState)
workflow.add_node("validate", validate_specs)
workflow.add_node("stress_test", perform_stress_test)
workflow.set_entry_point("validate")
workflow.add_edge("validate", "stress_test")
workflow.add_edge("stress_test", END)
graph = workflow.compile()

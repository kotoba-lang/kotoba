from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class HardwareState(TypedDict):
    part_number: str
    material_compliance: bool
    tensile_test_passed: bool
    log: List[str]

def validate_materials(state: HardwareState):
    # Simulate material analysis
    return {"material_compliance": True, "log": state.get("log", []) + ["Material verified"]}

def validate_specs(state: HardwareState):
    # Simulate stress testing
    return {"tensile_test_passed": True, "log": state.get("log", []) + ["Stress test passed"]}

workflow = StateGraph(HardwareState)
workflow.add_node("validate_materials", validate_materials)
workflow.add_node("validate_specs", validate_specs)
workflow.set_entry_point("validate_materials")
workflow.add_edge("validate_materials", "validate_specs")
workflow.add_edge("validate_specs", END)

graph = workflow.compile()

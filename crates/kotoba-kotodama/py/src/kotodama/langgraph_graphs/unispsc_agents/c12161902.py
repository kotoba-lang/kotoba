from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SubstrateState(TypedDict):
    material_id: str
    purity_check: bool
    thermal_validation: bool
    export_control_clearance: bool

def validate_purity(state: SubstrateState):
    # Simulate chemical analysis logic
    return {"purity_check": True}

def validate_thermal_specs(state: SubstrateState):
    # Simulate thermal property verification
    return {"thermal_validation": True}

def check_export_controls(state: SubstrateState):
    # Simulate dual-use verification logic
    return {"export_control_clearance": True}

graph = StateGraph(SubstrateState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("validate_thermal", validate_thermal_specs)
graph.add_node("check_export", check_export_controls)

graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "validate_thermal")
graph.add_edge("validate_thermal", "check_export")
graph.add_edge("check_export", END)

graph = graph.compile()

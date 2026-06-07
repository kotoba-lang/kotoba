from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrysuitState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_drysuit_specs(state: DrysuitState):
    specs = state.get('spec_data', {})
    # Logic to verify material and pressure testing
    is_compliant = "pressure_test_passed" in specs and specs.get("material") != "standard_fabric"
    return {"is_compliant": is_compliant}

workflow = StateGraph(DrysuitState)
workflow.add_node("validate_specs", validate_drysuit_specs)
workflow.set_entry_point("validate_specs")
workflow.add_edge("validate_specs", END)
graph = workflow.compile()

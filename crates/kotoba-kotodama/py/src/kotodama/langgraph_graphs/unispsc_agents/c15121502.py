from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SteelProcurementState(TypedDict):
    material_id: str
    specifications: dict
    validation_passed: bool
    inspection_log: List[str]

def validate_material_specs(state: SteelProcurementState):
    specs = state.get("specifications", {})
    # Simulated technical validation logic for cold-rolled steel
    passed = specs.get("tensile_strength_mpa", 0) >= 300
    return {"validation_passed": passed, "inspection_log": ["Material specification check completed"]}

def route_by_validation(state: SteelProcurementState):
    return "process" if state["validation_passed"] else "reject"

def process_steel_procurement(state: SteelProcurementState):
    return {"inspection_log": state["inspection_log"] + ["Processing procurement order for cold-rolled steel"]}

def reject_order(state: SteelProcurementState):
    return {"inspection_log": state["inspection_log"] + ["Order rejected due to non-compliant specifications"]}

graph = StateGraph(SteelProcurementState)
graph.add_node("validate", validate_material_specs)
graph.add_node("process", process_steel_procurement)
graph.add_node("reject", reject_order)
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", route_by_validation, {"process": "process", "reject": "reject"})
graph.add_edge("process", END)
graph.add_edge("reject", END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralFuelState(TypedDict):
    fuel_code: str
    quality_checks: List[str]
    compliance_status: bool
    final_report: str

def validate_fuel_spec(state: MineralFuelState):
    # Simulate spec validation logic
    checks = ['flash_point_verified', 'viscosity_verified']
    return {"quality_checks": checks, "compliance_status": True}

def generate_procurement_report(state: MineralFuelState):
    return {"final_report": "Validated for industrial standard procurement."}

graph = StateGraph(MineralFuelState)
graph.add_node("validate", validate_fuel_spec)
graph.add_node("finalize", generate_procurement_report)
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph.set_entry_point("validate")
graph = graph.compile()

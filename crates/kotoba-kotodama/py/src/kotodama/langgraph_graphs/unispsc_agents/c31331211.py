from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_number: str
    material_certified: bool
    inspection_passed: bool
    risk_cleared: bool

def check_material_cert(state: ProcurementState):
    return { "material_certified": True }

def perform_ndt_check(state: ProcurementState):
    return { "inspection_passed": True }

def validate_compliance(state: ProcurementState):
    return { "risk_cleared": True }

graph = StateGraph(ProcurementState)
graph.add_node("cert", check_material_cert)
graph.add_node("ndt", perform_ndt_check)
graph.add_node("compliance", validate_compliance)
graph.add_edge("cert", "ndt")
graph.add_edge("ndt", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("cert")
graph = graph.compile()

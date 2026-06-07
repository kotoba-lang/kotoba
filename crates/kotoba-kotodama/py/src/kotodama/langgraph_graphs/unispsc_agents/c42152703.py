from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    material_certified: bool
    sterility_report: str
    inspection_passed: bool

def validate_materials(state: DentalSupplyState):
    return {"material_certified": True}

def check_compliance(state: DentalSupplyState):
    return {"inspection_passed": True if state.get("sterility_report") == "ISO-PASS" else False}

graph = StateGraph(DentalSupplyState)
graph.add_node("validate", validate_materials)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

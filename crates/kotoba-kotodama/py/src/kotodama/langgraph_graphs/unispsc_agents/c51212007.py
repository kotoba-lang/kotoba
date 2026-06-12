from typing import TypedDict
from langgraph.graph import StateGraph, END

class GarlicProcurementState(TypedDict):
    origin_country: str
    pesticide_compliant: bool
    inspection_passed: bool

def validate_origin(state: GarlicProcurementState):
    return {"origin_country": state.get("origin_country", "Unknown")}

def check_quality(state: GarlicProcurementState):
    return {"inspection_passed": True if state.get("pesticide_compliant") else False}

graph = StateGraph(GarlicProcurementState)
graph.add_node("validate_origin", validate_origin)
graph.add_node("check_quality", check_quality)
graph.set_entry_point("validate_origin")
graph.add_edge("validate_origin", "check_quality")
graph.add_edge("check_quality", END)
graph = graph.compile()

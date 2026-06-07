from typing import TypedDict
from langgraph.graph import StateGraph, END

class MissileProcurementState(TypedDict):
    clearance_verified: bool
    export_approved: bool
    technical_specs: dict

def verify_clearance(state: MissileProcurementState):
    return {"clearance_verified": True}

def validate_export_regulations(state: MissileProcurementState):
    return {"export_approved": True}

graph = StateGraph(MissileProcurementState)
graph.add_node("clearance", verify_clearance)
graph.add_node("export_check", validate_export_regulations)
graph.add_edge("clearance", "export_check")
graph.add_edge("export_check", END)
graph.set_entry_point("clearance")
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END
class DiagnosticDeviceState(TypedDict):
    device_id: str
    quality_check_passed: bool
    compliance_validated: bool
def validate_compliance(state: DiagnosticDeviceState):
    return {"compliance_validated": True}
def perform_quality_inspection(state: DiagnosticDeviceState):
    return {"quality_check_passed": True}
graph = StateGraph(DiagnosticDeviceState)
graph.add_node("compliance_check", validate_compliance)
graph.add_node("quality_inspection", perform_quality_inspection)
graph.set_entry_point("compliance_check")
graph.add_edge("compliance_check", "quality_inspection")
graph.add_edge("quality_inspection", END)
graph = graph.compile()

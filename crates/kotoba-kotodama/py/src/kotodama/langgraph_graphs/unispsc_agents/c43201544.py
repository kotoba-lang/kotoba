from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LicenseState(TypedDict):
    license_id: str
    compliance_status: str
    usage_metrics: dict
    validation_logs: List[str]

def fetch_license_usage(state: LicenseState):
    # Simulate API call to license provider
    return {"usage_metrics": {"assigned_seats": 150, "active_seats": 120}}

def validate_compliance(state: LicenseState):
    status = "COMPLIANT" if state["usage_metrics"]["active_seats"] <= state["usage_metrics"]["assigned_seats"] else "NON_COMPLIANT"
    return {"compliance_status": status, "validation_logs": ["Compliance check executed successfully."]}

graph = StateGraph(LicenseState)
graph.add_node("fetch", fetch_license_usage)
graph.add_node("validate", validate_compliance)
graph.set_entry_point("fetch")
graph.add_edge("fetch", "validate")
graph.add_edge("validate", END)
graph = graph.compile()

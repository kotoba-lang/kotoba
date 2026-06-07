from typing import TypedDict
from langgraph.graph import StateGraph, END

class MedicalSpecState(TypedDict):
    item_id: str
    compliance_verified: bool
    optical_specs: dict
    approved: bool

def validate_certification(state: MedicalSpecState):
    return {"compliance_verified": True}

def check_optical_standards(state: MedicalSpecState):
    return {"approved": True}

workflow = StateGraph(MedicalSpecState)
workflow.add_node("validate_cert", validate_certification)
workflow.add_node("optical_check", check_optical_standards)
workflow.add_edge("validate_cert", "optical_check")
workflow.add_edge("optical_check", END)
workflow.set_entry_point("validate_cert")
graph = workflow.compile()

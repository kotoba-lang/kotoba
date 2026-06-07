from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    sterile_cert: bool
    passed_qa: bool

def check_sterile_certification(state: ProcurementState) -> dict:
    return {"sterile_cert": True if state.get("sterile_cert") else False}

def validate_qa_standards(state: ProcurementState) -> dict:
    passed = state.get("sterile_cert", False) == True
    return {"passed_qa": passed}

builder = StateGraph(ProcurementState)
builder.add_node("check_certs", check_sterile_certification)
builder.add_node("qa_check", validate_qa_standards)
builder.set_entry_point("check_certs")
builder.add_edge("check_certs", "qa_check")
builder.add_edge("qa_check", END)
graph = builder.compile()

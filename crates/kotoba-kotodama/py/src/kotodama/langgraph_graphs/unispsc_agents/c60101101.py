from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ReaderState(TypedDict):
    device_id: str
    spec_check: bool
    compliance_passed: bool

def validate_specs(state: ReaderState):
    return {"spec_check": True}

def verify_compliance(state: ReaderState):
    return {"compliance_passed": True}

graph = StateGraph(ReaderState)
graph.add_node("validate_specs", validate_specs)
graph.add_node("verify_compliance", verify_compliance)
graph.set_entry_point("validate_specs")
graph.add_edge("validate_specs", "verify_compliance")
graph.add_edge("verify_compliance", END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class ReconGraphState(TypedDict):
    airworthiness_valid: bool
    export_license_verified: bool
    status: str

def check_compliance(state: ReconGraphState):
    state['export_license_verified'] = True
    return {"status": "compliance_checked"}

def validate_specs(state: ReconGraphState):
    state['airworthiness_valid'] = True
    return {"status": "specs_validated"}

graph = StateGraph(ReconGraphState)
graph.add_node("compliance", check_compliance)
graph.add_node("specs", validate_specs)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "specs")
graph.add_edge("specs", END)
graph = graph.compile()

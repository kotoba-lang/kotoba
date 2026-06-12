from typing import TypedDict
from langgraph.graph import StateGraph, END

class AudioGearState(TypedDict):
    model_number: str
    spec_sheet_verified: bool
    compliance_checked: bool

def validate_specs(state: AudioGearState):
    return {"spec_sheet_verified": True}

def verify_compliance(state: AudioGearState):
    return {"compliance_checked": True}

graph = StateGraph(AudioGearState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", verify_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

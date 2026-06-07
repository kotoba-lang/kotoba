from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class ProcureState(TypedDict):
    item_id: str
    inspection_status: str
    compliance_score: int

def validate_medical_device(state: ProcureState):
    # Simulate stringent medical device inspection logic
    return {"inspection_status": "passed" if state.get("item_id") else "failed"}

def check_compliance(state: ProcureState):
    # Simulate regulatory check
    return {"compliance_score": 100}

graph = StateGraph(ProcureState)
graph.add_node("validate", validate_medical_device)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    equipment_id: str
    validation_checks: Annotated[list[str], operator.add]
    is_approved: bool

def validate_safety_certs(state: MiningState):
    return {"validation_checks": ["Safety certification verified"]}

def check_compliance(state: MiningState):
    return {"validation_checks": ["Export control clearance verified"], "is_approved": True}

graph = StateGraph(MiningState)
graph.add_node("safety", validate_safety_certs)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("safety")
graph.add_edge("safety", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

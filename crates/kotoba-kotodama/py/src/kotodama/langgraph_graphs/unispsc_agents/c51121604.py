from typing import TypedDict
from langgraph.graph import StateGraph, END

class PETNState(TypedDict):
    quantity: float
    license_verified: bool
    safety_clearance: bool

async def check_compliance(state: PETNState):
    state['license_verified'] = True
    return {'license_verified': True}

async def validate_safety(state: PETNState):
    state['safety_clearance'] = True
    return {'safety_clearance': True}

graph = StateGraph(PETNState)
graph.add_node("compliance", check_compliance)
graph.add_node("safety", validate_safety)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "safety")
graph.add_edge("safety", END)
graph = graph.compile()

from langgraph.graph import StateGraph, END
from typing import TypedDict

class KitState(TypedDict):
    kit_id: str
    contents_verified: bool
    compliance_ok: bool

def check_contents(state: KitState):
    state['contents_verified'] = True
    return state

def validate_compliance(state: KitState):
    state['compliance_ok'] = True
    return state

graph = StateGraph(KitState)
graph.add_node("verify", check_contents)
graph.add_node("compliance", validate_compliance)
graph.set_entry_point("verify")
graph.add_edge("verify", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

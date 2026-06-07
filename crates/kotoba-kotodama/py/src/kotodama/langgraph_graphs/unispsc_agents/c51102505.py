from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    purity: float
    safety_check: bool
    compliance_verified: bool

def validate_stability(state: ChemicalState):
    return {"safety_check": state.get("purity", 0) > 98.0}

def verify_regulations(state: ChemicalState):
    return {"compliance_verified": True}

graph = StateGraph(ChemicalState)
graph.add_node("stability", validate_stability)
graph.add_node("compliance", verify_regulations)
graph.set_entry_point("stability")
graph.add_edge("stability", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

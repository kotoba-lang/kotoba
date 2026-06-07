from typing import TypedDict
from langgraph.graph import StateGraph, END

class NuclearState(TypedDict):
    material_certified: bool
    safeguard_cleared: bool
    is_compliant: bool

def validate_materials(state: NuclearState):
    return {"material_certified": True}

def check_regulations(state: NuclearState):
    return {"safeguard_cleared": True, "is_compliant": True}

graph = StateGraph(NuclearState)
graph.add_node("validate", validate_materials)
graph.add_node("compliance", check_regulations)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

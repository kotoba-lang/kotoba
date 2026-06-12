from langgraph.graph import StateGraph, END
from typing import TypedDict

class PharmaState(TypedDict):
    purity_check: bool
    regulatory_approval: bool
    validated: bool

def validate_purity(state: PharmaState):
    return {"purity_check": True}

def check_regulations(state: PharmaState):
    return {"regulatory_approval": True}

def finalize_procurement(state: PharmaState):
    return {"validated": state["purity_check"] and state["regulatory_approval"]}

graph = StateGraph(PharmaState)
graph.add_node("purity", validate_purity)
graph.add_node("regs", check_regulations)
graph.add_node("finalize", finalize_procurement)
graph.add_edge("purity", "regs")
graph.add_edge("regs", "finalize")
graph.add_edge("finalize", END)
graph.set_entry_point("purity")
graph = graph.compile()

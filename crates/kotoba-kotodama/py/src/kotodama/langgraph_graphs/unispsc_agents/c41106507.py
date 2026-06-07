from typing import TypedDict
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    purity_validated: bool
    sterility_checked: bool
    is_approved: bool

def validate_purity(state: ReagentState):
    return {"purity_validated": True}

def check_sterility(state: ReagentState):
    return {"sterility_checked": True}

def approve_reagent(state: ReagentState):
    return {"is_approved": state["purity_validated"] and state["sterility_checked"]}

graph = StateGraph(ReagentState)
graph.add_node("purity", validate_purity)
graph.add_node("sterility", check_sterility)
graph.add_node("approval", approve_reagent)
graph.set_entry_point("purity")
graph.add_edge("purity", "sterility")
graph.add_edge("sterility", "approval")
graph.add_edge("approval", END)
graph = graph.compile()

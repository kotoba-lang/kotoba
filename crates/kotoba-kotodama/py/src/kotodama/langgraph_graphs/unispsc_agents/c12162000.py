from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    purity_check_passed: bool
    coa_validated: bool
    hazard_flag: bool

def validate_purity(state: ReagentState):
    return {"purity_check_passed": True}

def validate_coa(state: ReagentState):
    return {"coa_validated": True}

def check_hazards(state: ReagentState):
    return {"hazard_flag": False}

graph = StateGraph(ReagentState)
graph.add_node("purity", validate_purity)
graph.add_node("coa", validate_coa)
graph.add_node("hazards", check_hazards)
graph.set_entry_point("purity")
graph.add_edge("purity", "coa")
graph.add_edge("coa", "hazards")
graph.add_edge("hazards", END)
graph = graph.compile()

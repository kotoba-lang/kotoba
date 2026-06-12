from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    cas_number: str
    purity_level: float
    safety_check_passed: bool

def validate_cas(state: ReagentState):
    return {"safety_check_passed": state.get("cas_number") is not None}

def process_reagent(state: ReagentState):
    print(f"Processing chemical {state.get('cas_number')} with purity {state.get('purity_level')}")
    return {"safety_check_passed": True}

graph = StateGraph(ReagentState)
graph.add_node("validate", validate_cas)
graph.add_node("process", process_reagent)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()

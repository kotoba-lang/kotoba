from typing import TypedDict
from langgraph.graph import StateGraph, END

class JigState(TypedDict):
    spec_data: dict
    validation_results: list
    is_approved: bool

def validate_specs(state: JigState):
    specs = state.get("spec_data", {})
    results = ["Valid" if "tolerance" in specs else "Invalid Tolerance"]
    return {"validation_results": results}

def approval_node(state: JigState):
    return {"is_approved": all(res == "Valid" for res in state["validation_results"])}

graph = StateGraph(JigState)
graph.add_node("validate", validate_specs)
graph.add_node("approve", approval_node)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()

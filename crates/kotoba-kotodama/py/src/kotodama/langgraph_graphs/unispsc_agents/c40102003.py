from typing import TypedDict
from langgraph.graph import StateGraph, END

class BoilerState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_specs(state: BoilerState):
    specs = state.get("spec_data", {})
    required = ["pressure_rating", "voltage", "safety_cert"]
    passed = all(k in specs for k in required)
    return {"validation_passed": passed}

graph = StateGraph(BoilerState)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

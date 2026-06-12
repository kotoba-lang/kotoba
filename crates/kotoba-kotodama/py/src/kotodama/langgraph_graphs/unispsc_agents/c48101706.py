from typing import TypedDict
from langgraph.graph import StateGraph, END

class MilkshakeMachineState(TypedDict):
    model_number: str
    compliance_docs: bool
    is_food_safe: bool
    status: str

def validator(state: MilkshakeMachineState):
    if state.get("compliance_docs") and state.get("is_food_safe"):
        return {"status": "APPROVED"}
    return {"status": "REJECTED"}

graph = StateGraph(MilkshakeMachineState)
graph.add_node("validate", validator)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

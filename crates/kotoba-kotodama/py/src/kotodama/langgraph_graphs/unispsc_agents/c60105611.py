from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenMeasureState(TypedDict):
    material: str
    accuracy_check: bool
    compliance_docs: list

def validate_specs(state: KitchenMeasureState):
    return {"accuracy_check": state.get("accuracy_check", True)}

def check_compliance(state: KitchenMeasureState):
    return {"compliance_docs": ["FDA_COMPLIANT"]}

graph = StateGraph(KitchenMeasureState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()

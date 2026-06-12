from typing import TypedDict
from langgraph.graph import StateGraph, END

class FoodProcurementState(TypedDict):
    commodity_code: str
    inspection_passed: bool
    compliance_docs: list
    shipping_temp: float

def validate_food_safety(state: FoodProcurementState):
    return {"inspection_passed": True}

def check_compliance(state: FoodProcurementState):
    return {"compliance_docs": ["Certificate of Analysis", "HACCP"]}

graph = StateGraph(FoodProcurementState)
graph.add_node("validate", validate_food_safety)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()

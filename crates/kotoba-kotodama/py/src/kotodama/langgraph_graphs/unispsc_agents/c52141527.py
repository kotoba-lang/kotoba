from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class KitchenApplianceState(TypedDict):
    model_id: str
    safety_check_passed: bool
    compliance_docs: List[str]

def validate_safety_features(state: KitchenApplianceState):
    # logic for validating knife safety interlocks
    return {"safety_check_passed": True}

def verify_compliance(state: KitchenApplianceState):
    # logic for verifying PSE and Food Contact Material certifications
    return {"compliance_docs": ["PSE_Cert", "FoodSafe_Report"]}

graph_builder = StateGraph(KitchenApplianceState)
graph_builder.add_node("safety_check", validate_safety_features)
graph_builder.add_node("compliance", verify_compliance)
graph_builder.set_entry_point("safety_check")
graph_builder.add_edge("safety_check", "compliance")
graph_builder.add_edge("compliance", END)
graph = graph_builder.compile()

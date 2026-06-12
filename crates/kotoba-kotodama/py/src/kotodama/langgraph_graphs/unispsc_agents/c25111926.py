from typing import TypedDict
from langgraph.graph import StateGraph, END

class SailBattenState(TypedDict):
    specifications: dict
    validation_results: dict

def validate_materials(state: SailBattenState):
    # Simulate material compliance check
    return {"validation_results": {"material": "pass"}}

def check_flex_properties(state: SailBattenState):
    # Simulate flex stiffness validation
    return {"validation_results": {"flex": "pass"}}

graph = StateGraph(SailBattenState)
graph.add_node("material_check", validate_materials)
graph.add_node("flex_check", check_flex_properties)
graph.add_edge("material_check", "flex_check")
graph.add_edge("flex_check", END)
graph.set_entry_point("material_check")
graph = graph.compile()

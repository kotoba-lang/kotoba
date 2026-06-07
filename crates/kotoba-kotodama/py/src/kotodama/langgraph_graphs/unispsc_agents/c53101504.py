from typing import TypedDict
from langgraph.graph import StateGraph, END

class GarmentState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_materials(state: GarmentState):
    pass

def check_sizing(state: GarmentState):
    pass

graph = StateGraph(GarmentState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("check_sizing", check_sizing)
graph.add_edge("validate_materials", "check_sizing")
graph.add_edge("check_sizing", END)
graph.set_entry_point("validate_materials")
graph = graph.compile()

from langgraph.graph import StateGraph, END
from typing import TypedDict
class HeadlinerState(TypedDict):
    spec_data: dict
    approved: bool
    validation_log: list
def validate_materials(state: HeadlinerState):
    pass
def check_dimensions(state: HeadlinerState):
    pass
graph = StateGraph(HeadlinerState)
graph.add_node("material_check", validate_materials)
graph.add_node("dim_check", check_dimensions)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "dim_check")
graph.add_edge("dim_check", END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class DrillingState(TypedDict):
    bit_id: str
    material_specs: dict
    inspection_results: List[str]
    validation_passed: bool

def validate_material(state: DrillingState) -> DrillingState:
    # Simulate CAD/Material validation logic
    hardness = state.get("material_specs", {}).get("hardness", 0)
    state["validation_passed"] = hardness > 50
    return state

def check_wear_res(state: DrillingState) -> DrillingState:
    if state["validation_passed"]:
        state["inspection_results"].append("Wear resistance verified")
    return state

graph = StateGraph(DrillingState)
graph.add_node("validate", validate_material)
graph.add_node("inspect", check_wear_res)
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph.set_entry_point("validate")
graph = graph.compile()

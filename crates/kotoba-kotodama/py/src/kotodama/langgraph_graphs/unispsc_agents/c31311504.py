from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipeAssemblyState(TypedDict):
    material: str
    pressure_test_passed: bool
    weld_certified: bool

def validate_materials(state: PipeAssemblyState):
    return {"material": "Inconel-625" if not state.get("material") else state["material"]}

def check_quality(state: PipeAssemblyState):
    passed = state.get("pressure_test_passed", False) and state.get("weld_certified", False)
    return {"pressure_test_passed": passed}

graph = StateGraph(PipeAssemblyState)
graph.add_node("validate", validate_materials)
graph.add_node("quality_check", check_quality)
graph.set_entry_point("validate")
graph.add_edge("validate", "quality_check")
graph.add_edge("quality_check", END)
graph = graph.compile()

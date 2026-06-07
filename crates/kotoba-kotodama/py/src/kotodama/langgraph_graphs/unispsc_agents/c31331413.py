from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_certified: bool
    weld_inspection_passed: bool
    final_assembly: str

def validate_materials(state: AssemblyState):
    return {"material_certified": True}

def inspect_welds(state: AssemblyState):
    return {"weld_inspection_passed": True}

def assemble(state: AssemblyState):
    return {"final_assembly": "UV-Welded-Brass-Unit"}

graph = StateGraph(AssemblyState)
graph.add_node("validate", validate_materials)
graph.add_node("inspect", inspect_welds)
graph.add_node("assemble", assemble)
graph.set_entry_point("validate")
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", "assemble")
graph.add_edge("assemble", END)
graph = graph.compile()

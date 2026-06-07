from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MagnesiumProcessState(TypedDict):
    part_id: str
    material_certified: bool
    dimensional_check_passed: bool
    final_approval: bool

def validate_materials(state: MagnesiumProcessState):
    # Simulate material composition metallurgical check
    return {"material_certified": True}

def validate_dimensions(state: MagnesiumProcessState):
    # Simulate CAD/CMM verification logic
    return {"dimensional_check_passed": True}

def approve(state: MagnesiumProcessState):
    return {"final_approval": state['material_certified'] and state['dimensional_check_passed']}

graph = StateGraph(MagnesiumProcessState)
graph.add_node("MaterialCheck", validate_materials)
graph.add_node("DimensionCheck", validate_dimensions)
graph.add_node("Approval", approve)
graph.set_entry_point("MaterialCheck")
graph.add_edge("MaterialCheck", "DimensionCheck")
graph.add_edge("DimensionCheck", "Approval")
graph.add_edge("Approval", END)
graph = graph.compile()

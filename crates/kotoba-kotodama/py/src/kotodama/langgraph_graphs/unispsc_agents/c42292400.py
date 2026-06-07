from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalToolState(TypedDict):
    tool_id: str
    material_certified: bool
    sterilization_validated: bool
    inspection_passed: bool

def validate_material(state: SurgicalToolState):
    return {"material_certified": True}

def validate_sterility(state: SurgicalToolState):
    return {"sterilization_validated": True}

def perform_qc(state: SurgicalToolState):
    return {"inspection_passed": state["material_certified"] and state["sterilization_validated"]}

graph = StateGraph(SurgicalToolState)
graph.add_node("material", validate_material)
graph.add_node("sterility", validate_sterility)
graph.add_node("qc", perform_qc)
graph.set_entry_point("material")
graph.add_edge("material", "sterility")
graph.add_edge("sterility", "qc")
graph.add_edge("qc", END)
graph = graph.compile()

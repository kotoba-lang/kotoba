from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SurgicalInstrumentState(TypedDict):
    instrument_type: str
    material_compliance: bool
    sterility_check: bool
    approved: bool

def validate_material(state: SurgicalInstrumentState):
    return {"material_compliance": state.get("instrument_type") == "medical_grade_stainless"}

def check_sterility(state: SurgicalInstrumentState):
    return {"sterility_check": True}

def finalize_procurement(state: SurgicalInstrumentState):
    return {"approved": state["material_compliance"] and state["sterility_check"]}

graph = StateGraph(SurgicalInstrumentState)
graph.add_node("validate", validate_material)
graph.add_node("sterilize", check_sterility)
graph.add_node("approve", finalize_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterilize")
graph.add_edge("sterilize", "approve")
graph.add_edge("approve", END)
graph = graph.compile()

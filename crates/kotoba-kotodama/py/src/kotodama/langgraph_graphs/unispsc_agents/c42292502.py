from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalInstrumentState(TypedDict):
    instrument_id: str
    material_compliance: bool
    sterilization_validated: bool
    approved: bool

def validate_material(state: SurgicalInstrumentState):
    # Business logic for material validation (e.g. ASTM F899)
    return {"material_compliance": True}

def validate_sterilization(state: SurgicalInstrumentState):
    # Check sterilization documents
    return {"sterilization_validated": True}

def final_approval(state: SurgicalInstrumentState):
    approved = state["material_compliance"] and state["sterilization_validated"]
    return {"approved": approved}

graph = StateGraph(SurgicalInstrumentState)
graph.add_node("material_check", validate_material)
graph.add_node("sterilization_check", validate_sterilization)
graph.add_node("approval", final_approval)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "sterilization_check")
graph.add_edge("sterilization_check", "approval")
graph.add_edge("approval", END)
graph.add_edge("approval", END)

graph = graph.compile()

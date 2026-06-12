from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalToolState(TypedDict):
    material_info: str
    iso_compliant: bool
    approved: bool

def validate_iso(state: DentalToolState):
    state['iso_compliant'] = True # Mock validation
    return {'iso_compliant': True}

def approve_procurement(state: DentalToolState):
    state['approved'] = state.get('iso_compliant', False)
    return {'approved': state['approved']}

graph = StateGraph(DentalToolState)
graph.add_node("validate_iso", validate_iso)
graph.add_node("approve", approve_procurement)
graph.add_edge("validate_iso", "approve")
graph.add_edge("approve", END)
graph.set_entry_point("validate_iso")
graph = graph.compile()

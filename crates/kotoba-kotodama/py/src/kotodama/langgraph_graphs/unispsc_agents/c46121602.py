from typing import TypedDict
from langgraph.graph import StateGraph, END

class BoosterState(TypedDict):
    serial_number: str
    safety_certification: bool
    thrust_data: dict
    approved: bool

def validate_safety_compliance(state: BoosterState):
    # Simulate safety protocol validation for high-risk missile hardware
    state['approved'] = state.get('safety_certification', False) and 'thrust_data' in state
    return state

def check_export_controls(state: BoosterState):
    # Placeholder for ITAR/EAR compliance logic
    return {"export_compliant": True}

graph = StateGraph(BoosterState)
graph.add_node("safety_check", validate_safety_compliance)
graph.add_node("export_check", check_export_controls)
graph.set_entry_point("safety_check")
graph.add_edge("safety_check", "export_check")
graph.add_edge("export_check", END)
graph = graph.compile()

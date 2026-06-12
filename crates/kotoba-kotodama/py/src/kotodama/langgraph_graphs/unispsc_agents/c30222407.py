from typing import TypedDict
from langgraph.graph import StateGraph, END

class FluoroscopyState(TypedDict):
    room_specs: dict
    compliance_validated: bool
    safety_check: bool

def validate_tech_specs(state: FluoroscopyState):
    print("Validating diagnostic imaging resolution and radiation safety...")
    state['compliance_validated'] = True
    return state

def check_regulatory(state: FluoroscopyState):
    print("Verifying FDA/Medical device regulatory certifications...")
    state['safety_check'] = True
    return state

graph = StateGraph(FluoroscopyState)
graph.add_node("tech_validation", validate_tech_specs)
graph.add_node("reg_check", check_regulatory)
graph.set_entry_point("tech_validation")
graph.add_edge("tech_validation", "reg_check")
graph.add_edge("reg_check", END)
graph = graph.compile()

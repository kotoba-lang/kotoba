from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BloodCultureState(TypedDict):
    bottle_id: str
    media_type: str
    is_sterile: bool
    compliance_score: float

def validate_sterility(state: BloodCultureState) -> BloodCultureState:
    # Logic to verify sterilization certificate
    state['is_sterile'] = True
    return state

def check_regulatory_compliance(state: BloodCultureState) -> BloodCultureState:
    # Logic to check FDA/CE certification status
    state['compliance_score'] = 1.0
    return state

graph = StateGraph(BloodCultureState)
graph.add_node("validate_sterility", validate_sterility)
graph.add_node("check_compliance", check_regulatory_compliance)
graph.add_edge("validate_sterility", "check_compliance")
graph.add_edge("check_compliance", END)
graph.set_entry_point("validate_sterility")
graph = graph.compile()

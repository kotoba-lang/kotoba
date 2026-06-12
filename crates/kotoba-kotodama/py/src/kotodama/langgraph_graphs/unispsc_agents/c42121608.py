from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    product_id: str
    compliance_status: bool
    is_medical_grade: bool

def validate_compliance(state: DentalState):
    state['compliance_status'] = True
    return state

def check_medical_grade(state: DentalState):
    state['is_medical_grade'] = True
    return state

graph = StateGraph(DentalState)
graph.add_node("validate", validate_compliance)
graph.add_node("grade_check", check_medical_grade)
graph.set_entry_point("validate")
graph.add_edge("validate", "grade_check")
graph.add_edge("grade_check", END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class SuctionCatheterState(TypedDict):
    medical_grade: bool
    sterility_verified: bool
    quality_status: str

def validate_medical_compliance(state: SuctionCatheterState):
    state['medical_grade'] = True
    return state

def verify_sterilization_records(state: SuctionCatheterState):
    state['sterility_verified'] = True
    state['quality_status'] = 'CERTIFIED'
    return state

graph = StateGraph(SuctionCatheterState)
graph.add_node('validate', validate_medical_compliance)
graph.add_node('sterility', verify_sterilization_records)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()

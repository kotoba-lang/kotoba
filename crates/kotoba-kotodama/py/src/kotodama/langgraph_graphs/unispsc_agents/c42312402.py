from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MedicalSpecState(TypedDict):
    product_id: str
    material_certified: bool
    sterility_verified: bool
    compliance_score: int

def validate_biocompatibility(state: MedicalSpecState):
    state['material_certified'] = True
    return state

def check_sterilization(state: MedicalSpecState):
    state['sterility_verified'] = True
    return state

graph = StateGraph(MedicalSpecState)
graph.add_node('validate', validate_biocompatibility)
graph.add_node('sterilize', check_sterilization)
graph.add_edge('validate', 'sterilize')
graph.add_edge('sterilize', END)
graph.set_entry_point('validate')
graph = graph.compile()

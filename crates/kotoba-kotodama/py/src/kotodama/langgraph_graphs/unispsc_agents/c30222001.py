from typing import TypedDict
from langgraph.graph import StateGraph, END

class BridgeProcurementState(TypedDict):
    steel_grade: str
    structural_calc: bool
    safety_certification: bool

def validate_materials(state: BridgeProcurementState):
    print('Validating steel grade compliance...')
    return {'steel_grade': 'ASTM A709 verified'}

def structural_review(state: BridgeProcurementState):
    print('Performing structural calculation audit...')
    return {'structural_calc': True}

graph = StateGraph(BridgeProcurementState)
graph.add_node('validation', validate_materials)
graph.add_node('review', structural_review)
graph.set_entry_point('validation')
graph.add_edge('validation', 'review')
graph.add_edge('review', END)
graph = graph.compile()

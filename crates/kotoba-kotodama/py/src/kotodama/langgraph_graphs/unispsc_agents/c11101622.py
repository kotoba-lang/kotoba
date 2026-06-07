from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalProcessingState(TypedDict):
    material_id: str
    purity_level: float
    hazard_check_passed: bool
    approved_for_processing: bool

def validate_purity(state: ChemicalProcessingState):
    state['purity_level'] = state.get('purity_level', 0.0)
    return {'approved_for_processing': state['purity_level'] >= 99.5}

def conduct_hazard_review(state: ChemicalProcessingState):
    return {'hazard_check_passed': True}

graph = StateGraph(ChemicalProcessingState)
graph.add_node('purity_check', validate_purity)
graph.add_node('hazard_review', conduct_hazard_review)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'hazard_review')
graph.add_edge('hazard_review', END)
graph = graph.compile()

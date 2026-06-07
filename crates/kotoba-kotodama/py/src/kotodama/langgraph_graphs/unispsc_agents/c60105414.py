from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    compliance_score: float
    needs_pedagogical_review: bool

def validate_pedagogy(state: ProcurementState):
    state['needs_pedagogical_review'] = True
    return {'compliance_score': 0.95}

def finalize_procurement(state: ProcurementState):
    return {'compliance_score': 1.0}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_pedagogy)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

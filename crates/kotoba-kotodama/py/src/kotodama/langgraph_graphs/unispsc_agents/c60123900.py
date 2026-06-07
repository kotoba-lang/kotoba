from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_type: str
    quality_score: float
    compliance_ok: bool

def validate_material(state: ProcurementState):
    # Business logic for textile and trim validation
    is_compliant = state.get('material_type') in ['polyester', 'metal', 'plastic']
    return {'compliance_ok': is_compliant}

def assess_quality(state: ProcurementState):
    return {'quality_score': 0.95 if state['compliance_ok'] else 0.0}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('assess', assess_quality)
graph.add_edge('validate', 'assess')
graph.add_edge('assess', END)
graph.set_entry_point('validate')
graph = graph.compile()

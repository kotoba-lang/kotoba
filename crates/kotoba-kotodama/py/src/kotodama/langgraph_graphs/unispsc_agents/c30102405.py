from typing import TypedDict
from langgraph.graph import StateGraph, END

class SteelProcurementState(TypedDict):
    material_grade: str
    diameter_mm: float
    mill_cert_verified: bool

def validate_specs(state: SteelProcurementState):
    # Business logic for stainless steel rod certification checks
    if state.get('material_grade') in ['304', '316']:
        return {'mill_cert_verified': True}
    return {'mill_cert_verified': False}

graph = StateGraph(SteelProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

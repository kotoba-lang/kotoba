from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmaProcurementState(TypedDict):
    material_name: str
    quality_docs: list
    is_compliant: bool

def validate_gmp_certs(state: PharmaProcurementState):
    # Simulate regulatory validation logic
    certs = state.get('quality_docs', [])
    is_valid = len(certs) > 0 and 'GMP' in str(certs)
    return {'is_compliant': is_valid}

def route_by_compliance(state: PharmaProcurementState):
    return 'approved' if state['is_compliant'] else 'rejected'

graph = StateGraph(PharmaProcurementState)
graph.add_node('validate', validate_gmp_certs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

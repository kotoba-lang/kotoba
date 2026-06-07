from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    api_name: str
    purity: float
    gmp_compliant: bool
    validation_status: str

def validate_quality(state: ProcurementState):
    if state.get('purity', 0) < 99.0:
        return {'validation_status': 'FAILED_PURITY'}
    return {'validation_status': 'VERIFIED'}

def check_compliance(state: ProcurementState):
    if not state.get('gmp_compliant', False):
        return {'validation_status': 'FAILED_GMP'}
    return {'validation_status': 'READY_FOR_PROCUREMENT'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_quality)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity: float
    compliance_cert: bool
    approved: bool

def validate_quality(state: ProcurementState):
    is_pure = state.get('purity', 0) >= 99.0
    return {'approved': is_pure and state.get('compliance_cert', False)}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

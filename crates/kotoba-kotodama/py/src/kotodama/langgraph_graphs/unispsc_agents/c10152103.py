from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    inspection_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_sds(state: ProcurementState) -> ProcurementState:
    # Logic to verify SDS compliance
    return {'inspection_results': ['SDS verified']}

def check_purity(state: ProcurementState) -> ProcurementState:
    # Logic to verify chemical purity specs
    return {'inspection_results': ['Purity validated']}

def approve_procurement(state: ProcurementState) -> ProcurementState:
    return {'is_approved': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate_sds', validate_sds)
graph.add_node('check_purity', check_purity)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate_sds', 'check_purity')
graph.add_edge('check_purity', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate_sds')
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    quality_score: float
    inspection_passed: bool
    log_path: str

def validate_quality(state: ProcurementState) -> ProcurementState:
    if state.get('quality_score', 0) > 0.8:
        state['inspection_passed'] = True
    else:
        state['inspection_passed'] = False
    return state

def finalize_procurement(state: ProcurementState) -> ProcurementState:
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_quality)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

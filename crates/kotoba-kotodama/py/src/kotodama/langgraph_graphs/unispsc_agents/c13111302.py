from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CrudeState(TypedDict):
    site_id: str
    extraction_logs: List[str]
    compliance_score: float
    status: str

def validate_extraction(state: CrudeState) -> CrudeState:
    if not state.get('site_id'):
        state['status'] = 'FAILED_MISSING_ID'
    else:
        state['status'] = 'VALIDATED'
    return state

def run_compliance_check(state: CrudeState) -> CrudeState:
    state['compliance_score'] = 0.95
    return state

graph = StateGraph(CrudeState)
graph.add_node('validate', validate_extraction)
graph.add_node('compliance', run_compliance_check)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()

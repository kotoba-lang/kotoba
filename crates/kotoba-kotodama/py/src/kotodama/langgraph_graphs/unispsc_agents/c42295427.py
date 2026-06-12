from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalSupplyState(TypedDict):
    sterility_certificate_present: bool
    batch_id: str
    compliance_score: float

def validate_sterility(state: SurgicalSupplyState) -> SurgicalSupplyState:
    if not state.get('sterility_certificate_present'):
        state['compliance_score'] = 0.0
    else:
        state['compliance_score'] = 1.0
    return state

def check_qc_status(state: SurgicalSupplyState) -> str:
    return 'pass' if state['compliance_score'] > 0 else 'fail'

graph = StateGraph(SurgicalSupplyState)
graph.add_node('validate', validate_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

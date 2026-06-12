from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_ok: bool

def validate_stability(state: PharmState) -> PharmState:
    state['purity_check'] = True
    return state

def check_compliance(state: PharmState) -> PharmState:
    state['compliance_ok'] = True
    return state

graph = StateGraph(PharmState)
graph.add_node('stability', validate_stability)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('stability')
graph.add_edge('stability', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

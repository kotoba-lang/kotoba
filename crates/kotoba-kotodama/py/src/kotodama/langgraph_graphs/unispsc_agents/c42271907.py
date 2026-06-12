from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AspiratorState(TypedDict):
    device_id: str
    compliance_docs: List[str]
    verification_status: bool

def validate_compliance(state: AspiratorState):
    # Simulate regulatory validation logic for ISO/FDA docs
    docs = state.get('compliance_docs', [])
    is_valid = len(docs) >= 2
    return {'verification_status': is_valid}

def route_verification(state: AspiratorState):
    return 'pass' if state['verification_status'] else 'fail'

graph = StateGraph(AspiratorState)
graph.add_node('validate', validate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

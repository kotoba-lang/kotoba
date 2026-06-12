from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ReflexHammerState(TypedDict):
    item_id: str
    compliance_docs: List[str]
    is_validated: bool

def validate_medical_device(state: ReflexHammerState):
    # Business logic for medical device compliance check
    docs = state.get('compliance_docs', [])
    valid = 'ISO13485' in docs and 'FDA_Registration' in docs
    return {'is_validated': valid}

def route_verification(state: ReflexHammerState):
    return 'passed' if state['is_validated'] else 'failed'

graph = StateGraph(ReflexHammerState)
graph.add_node('validate', validate_medical_device)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

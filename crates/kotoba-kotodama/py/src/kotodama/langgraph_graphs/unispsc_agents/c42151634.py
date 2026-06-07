from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalToolState(TypedDict):
    item_id: str
    compliance_docs: List[str]
    is_approved: bool

def validate_compliance(state: DentalToolState):
    required = ['ISO_CERT', 'FDA_CLEARED']
    docs = state.get('compliance_docs', [])
    valid = all(doc in docs for doc in required)
    return {'is_approved': valid}

def route_by_validation(state: DentalToolState):
    return 'approved' if state['is_approved'] else END

graph = StateGraph(DentalToolState)
graph.add_node('validate', validate_compliance)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

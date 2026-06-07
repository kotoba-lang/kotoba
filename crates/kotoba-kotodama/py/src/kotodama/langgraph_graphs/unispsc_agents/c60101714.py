from langgraph.graph import StateGraph, END
from typing import TypedDict

class AuditState(TypedDict):
    resource_id: str
    compliance_score: float
    requires_review: bool

def check_compliance(state: AuditState):
    state['compliance_score'] = 1.0 if 'accessibility_format' in state else 0.5
    state['requires_review'] = state['compliance_score'] < 1.0
    return state

def route_review(state: AuditState):
    return 'review' if state['requires_review'] else END

graph = StateGraph(AuditState)
graph.add_node('compliance', check_compliance)
graph.add_edge('compliance', END)
graph.set_entry_point('compliance')
graph = graph.compile()

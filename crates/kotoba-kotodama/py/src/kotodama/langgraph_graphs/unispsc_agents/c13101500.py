from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CrudeOilState(TypedDict):
    commodity_code: str
    batch_id: str
    quality_metrics: dict
    compliance_status: List[str]
    approved: bool

def validate_compliance(state: CrudeOilState):
    metrics = state.get('quality_metrics', {})
    status = []
    if metrics.get('sulfur', 0) < 0.5:
        status.append('sulfur_ok')
    return {'compliance_status': status}

def decision_node(state: CrudeOilState):
    if 'sulfur_ok' in state['compliance_status']:
        return 'approve'
    return 'reject'

def approve_procurement(state: CrudeOilState):
    return {'approved': True}

def reject_procurement(state: CrudeOilState):
    return {'approved': False}

graph = StateGraph(CrudeOilState)
graph.add_node('validate', validate_compliance)
graph.add_node('approve', approve_procurement)
graph.add_node('reject', reject_procurement)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', decision_node, {'approve': 'approve', 'reject': 'reject'})
graph.add_edge('approve', END)
graph.add_edge('reject', END)
graph = graph.compile()

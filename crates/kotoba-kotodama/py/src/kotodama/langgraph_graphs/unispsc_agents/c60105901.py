from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EduMaterialState(TypedDict):
    content_id: str
    compliance_status: bool
    peer_review_data: dict
    approved: bool

def validate_content(state: EduMaterialState):
    # Simulate regulatory validation logic
    is_compliant = bool(state.get('content_id'))
    return {'compliance_status': is_compliant}

def approval_step(state: EduMaterialState):
    approval = state['compliance_status']
    return {'approved': approval}

graph = StateGraph(EduMaterialState)
graph.add_node('validate', validate_content)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

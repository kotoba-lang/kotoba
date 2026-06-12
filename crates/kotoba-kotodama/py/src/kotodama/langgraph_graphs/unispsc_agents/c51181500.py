from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MedState(TypedDict):
    medication_id: str
    batch_code: str
    compliance_checked: bool
    is_approved: bool

def validate_compliance(state: MedState):
    state['compliance_checked'] = True
    return {'compliance_checked': True}

def approval_check(state: MedState):
    state['is_approved'] = state['compliance_checked']
    return {'is_approved': state['is_approved']}

graph = StateGraph(MedState)
graph.add_node('validate', validate_compliance)
graph.add_node('approve', approval_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

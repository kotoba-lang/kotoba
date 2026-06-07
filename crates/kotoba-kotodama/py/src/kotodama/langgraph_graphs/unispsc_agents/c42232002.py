from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    compliance_checked: bool
    approved: bool

def validate_safety(state: ProcurementState):
    print('Validating medical compliance...')
    return {'compliance_checked': True}

def approval_check(state: ProcurementState):
    return {'approved': state['compliance_checked']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_safety)
graph.add_node('approve', approval_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()

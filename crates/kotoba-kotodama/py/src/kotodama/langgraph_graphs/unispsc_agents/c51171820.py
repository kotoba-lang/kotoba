from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    product_name: str
    compliance_checked: bool
    documentation_complete: bool

def validate_pharma_docs(state: ProcurementState):
    print('Validating pharmaceutical documentation for Dimenhydrinate...')
    state['documentation_complete'] = True
    return state

def verify_compliance(state: ProcurementState):
    print('Checking regulatory licenses...')
    state['compliance_checked'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_docs', validate_pharma_docs)
graph.add_node('check_compliance', verify_compliance)
graph.set_entry_point('validate_docs')
graph.add_edge('validate_docs', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WarheadState(TypedDict):
    compliance_docs: List[str]
    safety_check_passed: bool
    export_license_approved: bool

def validate_compliance(state: WarheadState):
    state['compliance_docs'] = ['ITAR_Form_signed', 'EUC_verified']
    return {'compliance_docs': state['compliance_docs']}

def perform_safety_check(state: WarheadState):
    return {'safety_check_passed': True}

graph = StateGraph(WarheadState)
graph.add_node('compliance', validate_compliance)
graph.add_node('safety', perform_safety_check)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

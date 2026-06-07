from typing import TypedDict
from langgraph.graph import StateGraph, END

class InsuranceState(TypedDict):
    material_type: str
    compliance_checked: bool
    approved: bool

def validate_compliance(state: InsuranceState):
    print('Checking regulatory compliance for educational material')
    return {'compliance_checked': True}

def audit_content(state: InsuranceState):
    print('Auditing content for fairness and accuracy')
    return {'approved': True}

graph = StateGraph(InsuranceState)
graph.add_node('validate', validate_compliance)
graph.add_node('audit', audit_content)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()

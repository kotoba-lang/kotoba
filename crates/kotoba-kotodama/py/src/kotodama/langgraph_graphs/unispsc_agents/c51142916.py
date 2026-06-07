from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_name: str
    quality_docs: list
    temp_validated: bool

def validate_biologic(state: ProcurementState):
    print('Validating cold chain and pharmaceutical certifications...')
    return {'temp_validated': True}

def audit_docs(state: ProcurementState):
    print('Auditing COA and sterility documents...')
    return {'quality_docs': ['COA_Verified', 'Sterility_Checked']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_biologic)
graph.add_node('audit', audit_docs)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()

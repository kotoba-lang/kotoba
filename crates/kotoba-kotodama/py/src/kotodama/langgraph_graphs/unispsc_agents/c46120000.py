from langgraph.graph import StateGraph, END
from typing import TypedDict

class MissileProcurementState(TypedDict):
    euc_verified: bool
    export_license: bool
    technical_review: bool

def verify_euc(state: MissileProcurementState):
    return {'euc_verified': True}

def check_export_compliance(state: MissileProcurementState):
    return {'export_license': True}

def technical_safety_review(state: MissileProcurementState):
    return {'technical_review': True}

graph = StateGraph(MissileProcurementState)
graph.add_node('verify_euc', verify_euc)
graph.add_node('export_compliance', check_export_compliance)
graph.add_node('technical_review', technical_safety_review)
graph.set_entry_point('verify_euc')
graph.add_edge('verify_euc', 'export_compliance')
graph.add_edge('export_compliance', 'technical_review')
graph.add_edge('technical_review', END)
graph = graph.compile()

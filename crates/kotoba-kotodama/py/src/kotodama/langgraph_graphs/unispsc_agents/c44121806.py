from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    compatibility_checked: bool
    compliance_verified: bool

def validate_compatibility(state: ProcurementState):
    print('Checking pen refill compatibility...')
    return {'compatibility_checked': True}

def verify_compliance(state: ProcurementState):
    print('Verifying chemical safety and shelf life...')
    return {'compliance_verified': True}

graph = StateGraph(ProcurementState)
graph.add_node('compatibility', validate_compatibility)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('compatibility')
graph.add_edge('compatibility', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

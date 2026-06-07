from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PaintStripperState(TypedDict):
    product_id: str
    sds_verified: bool
    voc_compliant: bool
    risk_level: str

def validate_safety_docs(state: PaintStripperState):
    state['sds_verified'] = True
    return state

def check_compliance(state: PaintStripperState):
    state['voc_compliant'] = True
    state['risk_level'] = 'high'
    return state

graph = StateGraph(PaintStripperState)
graph.add_node('validate_docs', validate_safety_docs)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_docs')
graph.add_edge('validate_docs', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

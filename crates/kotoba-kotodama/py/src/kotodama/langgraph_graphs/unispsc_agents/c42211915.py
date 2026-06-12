from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    item_id: str
    safety_check: bool
    compliance_validated: bool

def validate_safety(state: ProcessingState):
    return {'safety_check': True}

def validate_compliance(state: ProcessingState):
    return {'compliance_validated': True}

graph = StateGraph(ProcessingState)
graph.add_node('safety', validate_safety)
graph.add_node('compliance', validate_compliance)
graph.set_entry_point('safety')
graph.add_edge('safety', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

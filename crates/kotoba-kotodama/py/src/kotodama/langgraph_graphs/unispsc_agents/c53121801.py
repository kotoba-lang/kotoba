from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitState(TypedDict):
    kit_id: str
    compliance_passed: bool
    dimension_data: dict

def validate_dimensions(state: KitState):
    # Simulate check for carry-on size compliance
    return {'compliance_passed': True}

def audit_contents(state: KitState):
    return {'compliance_passed': True}

graph = StateGraph(KitState)
graph.add_node('validate', validate_dimensions)
graph.add_node('audit', audit_contents)
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph.set_entry_point('validate')
graph = graph.compile()

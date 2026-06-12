from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntistaticState(TypedDict):
    kit_id: str
    compliance_ok: bool
    validation_passed: bool

def validate_compliance(state: AntistaticState):
    return {'compliance_ok': True}

def audit_kit(state: AntistaticState):
    return {'validation_passed': True}

graph = StateGraph(AntistaticState)
graph.add_node('validate', validate_compliance)
graph.add_node('audit', audit_kit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()

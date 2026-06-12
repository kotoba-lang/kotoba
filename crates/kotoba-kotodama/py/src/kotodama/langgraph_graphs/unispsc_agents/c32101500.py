from typing import TypedDict
from langgraph.graph import StateGraph, END

class RFTaskState(TypedDict):
    part_number: str
    spec_check: bool
    compliance_verified: bool

def validate_specs(state: RFTaskState):
    state['spec_check'] = True
    return state

def verify_compliance(state: RFTaskState):
    state['compliance_verified'] = True
    return state

graph = StateGraph(RFTaskState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", verify_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

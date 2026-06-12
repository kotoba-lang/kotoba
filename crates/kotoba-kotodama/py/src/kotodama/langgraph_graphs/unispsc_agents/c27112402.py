from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_type: str
    spec_verified: bool
    compliance_check: bool

def validate_tool_specs(state: ToolState):
    state['spec_verified'] = True
    return {'spec_verified': True}

def perform_compliance_check(state: ToolState):
    state['compliance_check'] = True
    return {'compliance_check': True}

graph = StateGraph(ToolState)
graph.add_node("validate", validate_tool_specs)
graph.add_node("compliance", perform_compliance_check)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

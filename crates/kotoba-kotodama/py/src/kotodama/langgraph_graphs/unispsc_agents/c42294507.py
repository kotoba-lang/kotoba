from typing import TypedDict
from langgraph.graph import StateGraph, END

class OphthalmicToolState(TypedDict):
    tool_name: str
    is_sterile: bool
    compliance_verified: bool

def validate_certification(state: OphthalmicToolState):
    state['compliance_verified'] = True
    return state

def check_sterility(state: OphthalmicToolState):
    state['is_sterile'] = True
    return state

graph = StateGraph(OphthalmicToolState)
graph.add_node("validate", validate_certification)
graph.add_node("sterility", check_sterility)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterility")
graph.add_edge("sterility", END)
graph = graph.compile()

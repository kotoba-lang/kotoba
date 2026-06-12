from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class IgnitionState(TypedDict):
    part_number: str
    voltage_test: bool
    compliance_docs: List[str]
    approved: bool

def validate_part(state: IgnitionState):
    # Simulate CAD/Spec validation logic
    compliant = state.get('voltage_test', False) and len(state.get('compliance_docs', [])) > 0
    return {"approved": compliant}

graph = StateGraph(IgnitionState)
graph.add_node("validate", validate_part)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()

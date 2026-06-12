from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SystemState(TypedDict):
    assets: Annotated[Sequence[str], operator.add]
    compliance_status: dict
    tasks: Annotated[Sequence[str], operator.add]

def fetch_assets(state: SystemState):
    return {"assets": ["host-001", "host-002"]}

def validate_compliance(state: SystemState):
    return {"compliance_status": {"is_compliant": True}}

def execute_patching(state: SystemState):
    return {"tasks": ["apply-patch-001"]}

graph = StateGraph(SystemState)
graph.add_node("fetch", fetch_assets)
graph.add_node("validate", validate_compliance)
graph.add_node("patch", execute_patching)
graph.set_entry_point("fetch")
graph.add_edge("fetch", "validate")
graph.add_edge("validate", "patch")
graph.add_edge("patch", END)
graph = graph.compile()

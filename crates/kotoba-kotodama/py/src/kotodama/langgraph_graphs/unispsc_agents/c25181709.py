from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LoaderState(TypedDict):
    capacity_check: bool
    safety_compliance: bool
    inspection_report: str

def validate_specs(state: LoaderState):
    state['capacity_check'] = True
    return state

def safety_audit(state: LoaderState):
    state['safety_compliance'] = True
    return state

workflow = StateGraph(LoaderState)
workflow.add_node("validate", validate_specs)
workflow.add_node("audit", safety_audit)
workflow.add_edge("validate", "audit")
workflow.set_entry_point("validate")
workflow.add_edge("audit", END)
graph = workflow.compile()

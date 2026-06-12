from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WorkflowState(TypedDict):
    license_key: str
    compliance_checked: bool
    version_validated: bool

def validate_license(state: WorkflowState):
    return {'compliance_checked': True}

def check_compatibility(state: WorkflowState):
    return {'version_validated': True}

graph = StateGraph(WorkflowState)
graph.add_node('validate_license', validate_license)
graph.add_node('check_compatibility', check_compatibility)
graph.set_entry_point('validate_license')
graph.add_edge('validate_license', 'check_compatibility')
graph.add_edge('check_compatibility', END)

graph = graph.compile()

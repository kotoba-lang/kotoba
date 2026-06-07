from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class WasteWorkflowState(TypedDict):
    container_type: str
    spec_checked: bool
    compliance_validated: bool

def check_specs(state: WasteWorkflowState):
    # Simulate validation of puncture resistance certification
    state['spec_checked'] = True
    return state

def validate_compliance(state: WasteWorkflowState):
    # Verify biohazard marking compliance
    state['compliance_validated'] = True
    return state

graph = StateGraph(WasteWorkflowState)
graph.add_node('verify_specs', check_specs)
graph.add_node('validate_compliance', validate_compliance)
graph.set_entry_point('verify_specs')
graph.add_edge('verify_specs', 'validate_compliance')
graph.add_edge('validate_compliance', END)
graph = graph.compile()

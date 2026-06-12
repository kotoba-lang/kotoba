from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    model_id: str
    spec_verified: bool
    safety_audit_passed: bool

def validate_specs(state: RobotProcurementState):
    # Simulate CAD/Spec validation logic
    state['spec_verified'] = True
    return state

def run_safety_audit(state: RobotProcurementState):
    # Simulate regulatory safety checks
    state['safety_audit_passed'] = True
    return state

graph = StateGraph(RobotProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', run_safety_audit)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()

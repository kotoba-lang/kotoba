from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    model_id: str
    compliance_checked: bool
    safety_verified: bool

def validate_model(state: RobotProcurementState):
    return {'compliance_checked': True}

def verify_safety(state: RobotProcurementState):
    return {'safety_verified': True}

graph = StateGraph(RobotProcurementState)
graph.add_node('validate', validate_model)
graph.add_node('safety', verify_safety)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MotorState(TypedDict):
    part_number: str
    torque_requirements: float
    validation_errors: List[str]
    is_approved: bool

def validate_specs(state: MotorState):
    errors = []
    if state.get('torque_requirements', 0) < 0.5:
        errors.append('Insufficient torque for industrial arm')
    return {'validation_errors': errors, 'is_approved': len(errors) == 0}

def route_by_validation(state: MotorState):
    return 'approve' if state['is_approved'] else 'reject'

graph = StateGraph(MotorState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

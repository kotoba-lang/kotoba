from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ServoState(TypedDict):
    part_id: str
    specs: dict
    validation_logs: List[str]
    is_approved: bool

def validate_servo_specs(state: ServoState) -> ServoState:
    specs = state.get('specs', {})
    logs = []
    if specs.get('torque_nm', 0) <= 0:
        logs.append('Invalid torque specification.')
    if specs.get('ip_rating', 0) < 54:
        logs.append('Insufficient IP rating for industrial use.')
    state['validation_logs'] = logs
    state['is_approved'] = len(logs) == 0
    return state

def route_by_approval(state: ServoState) -> str:
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(ServoState)
graph.add_node('validate', validate_servo_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

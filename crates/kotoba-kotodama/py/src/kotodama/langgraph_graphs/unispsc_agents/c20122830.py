from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    part_id: str
    specs: dict
    validation_logs: List[str]
    is_approved: bool

def validate_specs(state: RobotState) -> RobotState:
    specs = state.get('specs', {})
    logs = []
    if specs.get('payload_capacity_kg', 0) <= 0:
        logs.append('Invalid payload capacity')
    state['validation_logs'] = logs
    state['is_approved'] = len(logs) == 0
    return state

def routing_logic(state: RobotState):
    return 'approved' if state['is_approved'] else END

builder = StateGraph(RobotState)
builder.add_node('validate', validate_specs)
builder.add_edge('validate', END)
builder.set_entry_point('validate')
graph = builder.compile()

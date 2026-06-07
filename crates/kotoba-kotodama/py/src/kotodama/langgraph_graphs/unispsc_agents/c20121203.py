from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    commodity_code: str
    spec_data: dict
    validation_log: List[str]
    is_approved: bool

def validate_effector_specs(state: RobotState) -> RobotState:
    specs = state.get('spec_data', {})
    log = []
    if specs.get('max_payload_kg', 0) <= 0:
        log.append('Invalid payload')
    state['validation_log'] = log
    state['is_approved'] = len(log) == 0
    return state

def assembly_workflow_step(state: RobotState) -> RobotState:
    if state.get('is_approved'):
        state['validation_log'].append('Workflow ready for deployment')
    return state

builder = StateGraph(RobotState)
builder.add_node('validate', validate_effector_specs)
builder.add_node('workflow', assembly_workflow_step)
builder.add_edge('validate', 'workflow')
builder.add_edge('workflow', END)
builder.set_entry_point('validate')
graph = builder.compile()

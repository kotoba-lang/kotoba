from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END

class HardwareState(TypedDict):
    part_id: str
    specs: dict
    validation_logs: List[str]
    is_approved: bool

def validate_specs(state: HardwareState):
    logs = state.get('validation_logs', [])
    logs.append('Dimensional tolerances verified.')
    return {'validation_logs': logs}

def check_compliance(state: HardwareState):
    logs = state.get('validation_logs', [])
    logs.append('Compliance with material standards confirmed.')
    return {'validation_logs': logs, 'is_approved': True}

builder = StateGraph(HardwareState)
builder.add_node('validate', validate_specs)
builder.add_node('compliance', check_compliance)
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
builder.set_entry_point('validate')
graph = builder.compile()

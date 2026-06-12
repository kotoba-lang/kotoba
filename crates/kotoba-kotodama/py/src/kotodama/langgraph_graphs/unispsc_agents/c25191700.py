from typing import TypedDict
from langgraph.graph import StateGraph, END

class EquipmentState(TypedDict):
    equipment_id: str
    is_calibrated: bool
    safety_passed: bool

def validate_specs(state: EquipmentState):
    state['safety_passed'] = True
    return state

def run_compliance_check(state: EquipmentState):
    state['is_calibrated'] = True
    return state

builder = StateGraph(EquipmentState)
builder.add_node('validate', validate_specs)
builder.add_node('compliance', run_compliance_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
graph = builder.compile()

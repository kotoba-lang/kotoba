from typing import TypedDict
from langgraph.graph import StateGraph, END

class IPPBState(TypedDict):
    device_id: str
    compliance_docs: list
    pressure_test_passed: bool

def validate_compliance(state: IPPBState):
    state['compliance_docs'] = ['ISO_13485', 'FDA_Clearance']
    return state

def perform_calibration(state: IPPBState):
    state['pressure_test_passed'] = True
    return state

builder = StateGraph(IPPBState)
builder.add_node('validate', validate_compliance)
builder.add_node('calibrate', perform_calibration)
builder.add_edge('validate', 'calibrate')
builder.add_edge('calibrate', END)
builder.set_entry_point('validate')
graph = builder.compile()

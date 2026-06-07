from typing import TypedDict
from langgraph.graph import StateGraph, END

class TransilluminatorState(TypedDict):
    device_id: str
    compliance_passed: bool
    light_intensity_ok: bool

def validate_medical_device(state: TransilluminatorState):
    # Simulate regulatory compliance check
    print('Validating ISO 13485 certification...')
    state['compliance_passed'] = True
    return state

def check_intensity(state: TransilluminatorState):
    # Simulate light output verification
    print('Verifying lumen output parameters...')
    state['light_intensity_ok'] = True
    return state

builder = StateGraph(TransilluminatorState)
builder.add_node('validate', validate_medical_device)
builder.add_node('intensity_check', check_intensity)
builder.set_entry_point('validate')
builder.add_edge('validate', 'intensity_check')
builder.add_edge('intensity_check', END)
graph = builder.compile()

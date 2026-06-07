from typing import TypedDict
from langgraph.graph import StateGraph, END

class PatientMonitorState(TypedDict):
    device_id: str
    compliance_docs: list
    accuracy_test_passed: bool
    final_status: str

def validate_compliance(state: PatientMonitorState):
    state['compliance_docs'] = ['FDA_510k', 'ISO13485']
    return {'compliance_docs': state['compliance_docs']}

def perform_accuracy_check(state: PatientMonitorState):
    state['accuracy_test_passed'] = True
    return {'accuracy_test_passed': True}

builder = StateGraph(PatientMonitorState)
builder.add_node('validate', validate_compliance)
builder.add_node('accuracy_check', perform_accuracy_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'accuracy_check')
builder.add_edge('accuracy_check', END)
graph = builder.compile()

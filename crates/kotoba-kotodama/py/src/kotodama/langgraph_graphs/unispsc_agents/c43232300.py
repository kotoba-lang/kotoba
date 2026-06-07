from typing import TypedDict
from langgraph.graph import StateGraph, END

class DataSoftwareState(TypedDict):
    license_type: str
    compliance_checked: bool
    deployment_model: str

def validate_compliance(state: DataSoftwareState):
    print('Checking data sovereignty and compliance...')
    return {'compliance_checked': True}

def setup_workflow(state: DataSoftwareState):
    print('Configuring provisioning workflow...')
    return {'status': 'configured'}

builder = StateGraph(DataSoftwareState)
builder.add_node('validate', validate_compliance)
builder.add_node('setup', setup_workflow)
builder.add_edge('validate', 'setup')
builder.set_entry_point('validate')
builder.add_edge('setup', END)
graph = builder.compile()

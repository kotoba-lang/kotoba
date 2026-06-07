from typing import TypedDict
from langgraph.graph import StateGraph, END

class CallSystemState(TypedDict):
    system_id: str
    config_verified: bool
    compliance_ok: bool

def validate_config(state: CallSystemState):
    print(f'Validating configuration for {state.get(system_id)}')
    return {'config_verified': True}

def check_compliance(state: CallSystemState):
    print('Checking regulatory compliance for call logging...')
    return {'compliance_ok': True}

workflow = StateGraph(CallSystemState)
workflow.add_node('validate', validate_config)
workflow.add_node('compliance', check_compliance)
workflow.add_edge('validate', 'compliance')
workflow.add_edge('compliance', END)
workflow.set_entry_point('validate')
graph = workflow.compile()

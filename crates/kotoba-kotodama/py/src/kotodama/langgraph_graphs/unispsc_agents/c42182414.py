from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TinnitusDeviceState(TypedDict):
    device_id: str
    calibration_data: dict
    compliance_checks: List[str]
    approved: bool

def validate_specs(state: TinnitusDeviceState):
    checks = []
    if 'calibration_certificate' in state.get('calibration_data', {}):
        checks.append('Calibration verified')
    return {'compliance_checks': checks}

def approval_logic(state: TinnitusDeviceState):
    is_approved = len(state['compliance_checks']) >= 1
    return {'approved': is_approved}

workflow = StateGraph(TinnitusDeviceState)
workflow.add_node('validation', validate_specs)
workflow.add_node('approval', approval_logic)
workflow.set_entry_point('validation')
workflow.add_edge('validation', 'approval')
workflow.add_edge('approval', END)
graph = workflow.compile()

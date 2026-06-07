from typing import TypedDict
from langgraph.graph import StateGraph, END

class BackstopState(TypedDict):
    spec_data: dict
    validated: bool
    error_msg: str

def validate_specs(state: BackstopState):
    specs = state.get('spec_data', {})
    if 'torque_capacity_nm' in specs and specs['torque_capacity_nm'] > 0:
        return {'validated': True}
    return {'validated': False, 'error_msg': 'Invalid torque specification'}

workflow = StateGraph(BackstopState)
workflow.add_node('validation', validate_specs)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()

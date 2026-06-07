from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ComponentState(TypedDict):
    component_id: str
    spec_requirements: dict
    validation_passed: bool
    inspection_log: List[str]

def validate_specs(state: ComponentState) -> ComponentState:
    requirements = state.get('spec_requirements', {})
    # Logic to validate tolerances and material specs
    if 'tolerance' in requirements:
        state['validation_passed'] = True
        state['inspection_log'].append('Tolerance check passed.')
    else:
        state['validation_passed'] = False
    return state

def assembly_ready(state: ComponentState) -> str:
    return 'APPROVED' if state['validation_passed'] else 'REJECTED'

workflow = StateGraph(ComponentState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_conditional_edges('validate', assembly_ready, {'APPROVED': END, 'REJECTED': END})

graph = workflow.compile()

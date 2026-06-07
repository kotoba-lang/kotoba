from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MotorState(TypedDict):
    specs: dict
    validation_passed: bool
    errors: List[str]

def validate_torque_specs(state: MotorState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('rated_torque', 0) <= 0:
        errors.append('Invalid rated torque')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

workflow = StateGraph(MotorState)
workflow.add_node('validate', validate_torque_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()

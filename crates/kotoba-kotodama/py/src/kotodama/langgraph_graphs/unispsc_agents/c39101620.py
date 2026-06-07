from typing import TypedDict
from langgraph.graph import StateGraph, END

class LampState(TypedDict):
    specs: dict
    validation_passed: bool
    error_log: list

def validate_lamp_specs(state: LampState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('rated_lifespan', 0) < 60000:
        errors.append('Lifespan below industry standard for induction lamps.')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: LampState):
    return 'pass' if state['validation_passed'] else 'fail'

workflow = StateGraph(LampState)
workflow.add_node('validate', validate_lamp_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()

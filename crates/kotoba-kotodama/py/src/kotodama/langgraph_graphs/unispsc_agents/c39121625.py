from typing import TypedDict
from langgraph.graph import StateGraph, END

class FuseState(TypedDict):
    specifications: dict
    validation_passed: bool
    error_log: list

def validate_fuse_specs(state: FuseState):
    specs = state.get('specifications', {})
    errors = []
    if specs.get('rated_voltage', 0) <= 0:
        errors.append('Invalid Rated Voltage')
    if specs.get('interrupting_rating', 0) < 10000:
        errors.append('Interrupting Rating below industrial thresholds')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

workflow = StateGraph(FuseState)
workflow.add_node('validate', validate_fuse_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()

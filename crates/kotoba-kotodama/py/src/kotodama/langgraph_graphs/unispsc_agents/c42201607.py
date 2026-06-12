from typing import TypedDict
from langgraph.graph import StateGraph, END

class MRIState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: MRIState):
    specs = state.get('spec_data', {})
    errors = []
    if not specs.get('dicom_compliance', False):
        errors.append('DICOM Part 14 verification failed')
    if specs.get('luminance', 0) < 500:
        errors.append('Luminance below medical-grade threshold')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route(state: MRIState):
    return 'pass' if state['validation_passed'] else 'fail'

graph = StateGraph(MRIState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

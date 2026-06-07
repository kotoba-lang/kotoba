from typing import TypedDict
from langgraph.graph import StateGraph, END

class FreezeDryerState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: FreezeDryerState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('condenser_temperature_celsius', 0) > -50:
        errors.append('Condenser temperature too high for lyophilization')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: FreezeDryerState):
    return 'process' if state['validation_passed'] else 'reject'

graph = StateGraph(FreezeDryerState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation, {'process': END, 'reject': END})
graph = graph.compile()

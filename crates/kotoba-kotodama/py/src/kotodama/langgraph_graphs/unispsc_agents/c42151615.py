from typing import TypedDict
from langgraph.graph import StateGraph, END

class WorkflowState(TypedDict):
    device_specs: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: WorkflowState):
    specs = state.get('device_specs', {})
    errors = []
    if 'temperature_range' not in specs: errors.append('Temperature range missing')
    if 'regulatory_id' not in specs: errors.append('Regulatory ID missing')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: WorkflowState):
    return 'process' if state['validation_passed'] else END

def process_cryo_unit(state: WorkflowState):
    print('Processing dental cryosurgical unit deployment workflows...')
    return {'validation_passed': True}

graph = StateGraph(WorkflowState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_cryo_unit)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()

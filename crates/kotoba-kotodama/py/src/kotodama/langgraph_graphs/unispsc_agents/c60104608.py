from typing import TypedDict
from langgraph.graph import StateGraph, END

class TorqueState(TypedDict):
    spec_data: dict
    validation_result: bool
    error_log: list

def validate_specs(state: TorqueState):
    specs = state.get('spec_data', {})
    required = ['torque_range_nm', 'accuracy_class']
    valid = all(k in specs for k in required)
    return {'validation_result': valid, 'error_log': [] if valid else ['Missing technical specs']}

def process_calibration(state: TorqueState):
    return {'error_log': state['error_log'] + ['Calibration test queued']}

graph = StateGraph(TorqueState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', process_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()

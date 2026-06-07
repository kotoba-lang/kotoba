from typing import TypedDict
from langgraph.graph import StateGraph, END

class SensorState(TypedDict):
    sensor_model: str
    validation_checks: list
    calibration_status: bool

def validate_specs(state: SensorState):
    print(f'Validating specs for {state.get('sensor_model')}')
    return {'validation_checks': ['range_check', 'ip_rating_verified']}

def check_compliance(state: SensorState):
    print('Checking dual-use compliance...')
    return {'calibration_status': True}

graph = StateGraph(SensorState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

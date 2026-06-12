from typing import TypedDict
from langgraph.graph import StateGraph, END

class PneumotachState(TypedDict):
    calibration_data: dict
    validation_passed: bool

def validate_sensor_spec(state: PneumotachState):
    # Simulate flow accuracy check
    accuracy = state.get('calibration_data', {}).get('accuracy', 0.0)
    return {'validation_passed': accuracy < 0.02}

def route_by_validation(state: PneumotachState):
    return 'process' if state['validation_passed'] else 'reject'

graph = StateGraph(PneumotachState)
graph.add_node('validate', validate_sensor_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

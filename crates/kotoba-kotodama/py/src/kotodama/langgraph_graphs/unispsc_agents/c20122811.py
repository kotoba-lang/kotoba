from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SensorProcessState(TypedDict):
    sensor_id: str
    spec_compliance: bool
    test_results: Annotated[Sequence[str], operator.add]

def validate_sensor_specs(state: SensorProcessState):
    # Simulate validation logic for procurement
    return {test_results: [f'Validated specs for {state[sensor_id]}']}

def perform_calibration_check(state: SensorProcessState):
    return {test_results: ['Calibration pass']}

builder = StateGraph(SensorProcessState)
builder.add_node('validate', validate_sensor_specs)
builder.add_node('calibrate', perform_calibration_check)
builder.add_edge('validate', 'calibrate')
builder.add_edge('calibrate', END)
builder.set_entry_point('validate')
graph = builder.compile()

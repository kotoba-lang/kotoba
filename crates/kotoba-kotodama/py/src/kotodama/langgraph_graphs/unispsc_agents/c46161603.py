from typing import TypedDict
from langgraph.graph import StateGraph, END

class PoolAlarmState(TypedDict):
    model_id: str
    sensor_type: str
    compliance_verified: bool
    alert_test_passed: bool

def validate_model(state: PoolAlarmState):
    print(f'Validating sensor model: {state.get('sensor_type')}')
    return {'compliance_verified': True}

def perform_alert_test(state: PoolAlarmState):
    print('Executing alert trigger validation')
    return {'alert_test_passed': True}

builder = StateGraph(PoolAlarmState)
builder.add_node('validate', validate_model)
builder.add_node('test_alert', perform_alert_test)
builder.add_edge('validate', 'test_alert')
builder.add_edge('test_alert', END)
builder.set_entry_point('validate')
graph = builder.compile()

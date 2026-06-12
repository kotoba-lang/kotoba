from typing import TypedDict
from langgraph.graph import StateGraph, END

class TapeTesterState(TypedDict):
    device_id: str
    calibration_data: dict
    validation_status: bool

def validate_calibration(state: TapeTesterState):
    # Simulate logic to verify calibration certificate
    is_valid = 'cert' in state.get('calibration_data', {})
    return {'validation_status': is_valid}

def route_by_status(state: TapeTesterState):
    return 'process' if state['validation_status'] else END

def process_testing(state: TapeTesterState):
    print(f'Initializing tape speed testing for: {state.get(device_id)}')
    return {'validation_status': True}

graph = StateGraph(TapeTesterState)
graph.add_node('validate', validate_calibration)
graph.add_node('process', process_testing)
graph.add_edge('validate', 'process')
graph.set_entry_point('validate')
graph.add_edge('process', END)
graph = graph.compile()

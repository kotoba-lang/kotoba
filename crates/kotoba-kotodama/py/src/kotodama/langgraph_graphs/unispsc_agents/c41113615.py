from typing import TypedDict
from langgraph.graph import StateGraph, END

class ElectrometerState(TypedDict):
    device_id: str
    calibration_status: bool
    input_check: str

def validate_specs(state: ElectrometerState) -> ElectrometerState:
    if not state.get('calibration_status'):
        state['input_check'] = 'MISSING_CALIBRATION'
    else:
        state['input_check'] = 'PASSED'
    return state

def run_diagnostics(state: ElectrometerState) -> ElectrometerState:
    state['input_check'] = 'DIAGNOSTICS_COMPLETE'
    return state

graph = StateGraph(ElectrometerState)
graph.add_node('validate', validate_specs)
graph.add_node('diagnostics', run_diagnostics)
graph.set_entry_point('validate')
graph.add_edge('validate', 'diagnostics')
graph.add_edge('diagnostics', END)
graph = graph.compile()

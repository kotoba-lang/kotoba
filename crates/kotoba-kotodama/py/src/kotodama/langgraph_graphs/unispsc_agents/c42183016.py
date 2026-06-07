from typing import TypedDict
from langgraph.graph import StateGraph, END

class OphthalmicSpecState(TypedDict):
    device_id: str
    calibration_status: bool
    compliance_passed: bool

def validate_specs(state: OphthalmicSpecState):
    state['compliance_passed'] = state.get('calibration_status', False)
    print(f'Validating specs for {state.get('device_id')}')
    return state

graph = StateGraph(OphthalmicSpecState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

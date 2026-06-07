from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WeatherStationState(TypedDict):
    sensor_specs: dict
    calibration_status: bool
    compliance_tags: List[str]

def validate_specs(state: WeatherStationState):
    specs = state.get('sensor_specs', {})
    state['compliance_tags'] = ['sensor_validated'] if specs.get('accuracy') else ['validation_failed']
    return state

def check_compliance(state: WeatherStationState):
    if 'sensor_validated' in state.get('compliance_tags', []):
        state['calibration_status'] = True
    return state

graph = StateGraph(WeatherStationState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

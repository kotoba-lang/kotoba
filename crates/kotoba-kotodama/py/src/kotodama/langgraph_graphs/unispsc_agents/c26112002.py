from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrivenPlateState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: DrivenPlateState) -> DrivenPlateState:
    specs = state.get('spec_data', {})
    checks = ['Friction Coefficient', 'Spline Dimensions']
    state['validation_passed'] = all(k in specs for k in checks)
    return state

def check_thermal_rating(state: DrivenPlateState) -> DrivenPlateState:
    if state.get('validation_passed'):
        state['validation_passed'] = state['spec_data'].get('Thermal Rating', 0) > 500
    return state

graph = StateGraph(DrivenPlateState)
graph.add_node('validate', validate_specs)
graph.add_node('thermal_check', check_thermal_rating)
graph.set_entry_point('validate')
graph.add_edge('validate', 'thermal_check')
graph.add_edge('thermal_check', END)
graph = graph.compile()

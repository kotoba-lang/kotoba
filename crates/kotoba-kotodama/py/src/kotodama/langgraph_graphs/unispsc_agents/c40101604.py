from typing import TypedDict
from langgraph.graph import StateGraph, END

class FanProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_fan_specs(state: FanProcurementState):
    specs = state.get('spec_data', {})
    # Check for required efficiency and safety standards
    passed = 'airflow_cfm' in specs and 'power_watts' in specs and specs['power_watts'] < 2000
    return {'validation_passed': passed}

def route_by_validation(state: FanProcurementState):
    return 'valid' if state['validation_passed'] else 'invalid'

graph = StateGraph(FanProcurementState)
graph.add_node('validate', validate_fan_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

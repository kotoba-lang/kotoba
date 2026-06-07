from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnalysisState(TypedDict):
    analyzer_specs: dict
    validation_passed: bool

def validate_specs(state: AnalysisState):
    specs = state.get('analyzer_specs', {})
    # Check for required calibration compliance
    is_valid = 'calibration_standard' in specs and specs['detection_limit'] < 0.1
    return {'validation_passed': is_valid}

def route_procurement(state: AnalysisState):
    return 'process' if state['validation_passed'] else 'reject'

graph = StateGraph(AnalysisState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

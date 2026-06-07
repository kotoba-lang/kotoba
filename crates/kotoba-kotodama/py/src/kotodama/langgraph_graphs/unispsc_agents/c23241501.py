from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingGraphState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: WeldingGraphState):
    specs = state.get('spec_data', {})
    checks = [specs.get('power_kw', 0) > 0, 'safety_standard' in specs]
    return {'validation_passed': all(checks), 'error_log': [] if all(checks) else ['Missing spec coverage']}

def route_by_validation(state: WeldingGraphState):
    return 'validate' if not state.get('validation_passed') else END

graph = StateGraph(WeldingGraphState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

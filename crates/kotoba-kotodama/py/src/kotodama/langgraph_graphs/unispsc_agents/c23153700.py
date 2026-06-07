from typing import TypedDict
from langgraph.graph import StateGraph, END

class AutomationState(TypedDict):
    controller_specs: dict
    validation_passed: bool
    error_reports: list

def validate_controller_specs(state: AutomationState):
    # Logic for spec validation
    return {'validation_passed': True}

def route_by_validation(state: AutomationState):
    return 'process' if state['validation_passed'] else END

def process_controller(state: AutomationState):
    return {'error_reports': ['None']}

graph = StateGraph(AutomationState)
graph.add_node('validate', validate_controller_specs)
graph.add_node('process', process_controller)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

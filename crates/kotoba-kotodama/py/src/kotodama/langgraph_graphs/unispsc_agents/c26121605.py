from typing import TypedDict
from langgraph.graph import StateGraph, END

class CableState(TypedDict):
    spec_data: dict
    compliance_passed: bool
    validation_log: list

def validate_specs(state: CableState):
    specs = state.get('spec_data', {})
    log = []
    passed = True
    if specs.get('voltage_rating', 0) < 600:
        log.append('Low voltage rating for aero applications')
        passed = False
    return {'compliance_passed': passed, 'validation_log': log}

def route_verification(state: CableState):
    return 'pass' if state['compliance_passed'] else 'fail'

graph = StateGraph(CableState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

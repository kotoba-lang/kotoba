from typing import TypedDict
from langgraph.graph import StateGraph, END

class GrindingState(TypedDict):
    machine_specs: dict
    validation_passed: bool
    compliance_tags: list

def validate_tech(state: GrindingState):
    specs = state.get('machine_specs', {})
    # Logic for dual-use export control checks based on RPM and accuracy
    passed = specs.get('accuracy', 10) < 5 and specs.get('axes', 0) >= 3
    return {'validation_passed': passed}

def route_compliance(state: GrindingState):
    return 'compliant' if state['validation_passed'] else 'restricted'

graph = StateGraph(GrindingState)
graph.add_node('validate', validate_tech)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

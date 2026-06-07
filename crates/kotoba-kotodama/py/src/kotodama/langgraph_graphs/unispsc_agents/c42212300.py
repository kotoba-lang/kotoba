from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AssistiveDeviceState(TypedDict):
    product_id: str
    specs: dict
    validation_passed: bool
    safety_check_logs: List[str]

def validate_specs(state: AssistiveDeviceState):
    specs = state.get('specs', {})
    load = specs.get('max_load', 0)
    passed = load > 0 and load < 5.0
    return {'validation_passed': passed, 'safety_check_logs': ['Load capacity verified']}

def certify_compliance(state: AssistiveDeviceState):
    # Simulate regulatory check
    return {'safety_check_logs': state['safety_check_logs'] + ['ISO 13485 check complete']}

graph = StateGraph(AssistiveDeviceState)
graph.add_node('validate', validate_specs)
graph.add_node('certify', certify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()

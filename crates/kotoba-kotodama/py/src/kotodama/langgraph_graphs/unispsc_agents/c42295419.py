from typing import TypedDict
from langgraph.graph import StateGraph, END

class NerveStimulatorState(TypedDict):
    device_id: str
    spec_valid: bool
    safety_check_passed: bool

def validate_specs(state: NerveStimulatorState):
    # Simulate specification validation logic
    state['spec_valid'] = True
    return state

def run_safety_audit(state: NerveStimulatorState):
    # Simulate medical safety audit
    state['safety_check_passed'] = True
    return state

graph = StateGraph(NerveStimulatorState)
graph.add_node('validate', validate_specs)
graph.add_node('safety_audit', run_safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety_audit')
graph.add_edge('safety_audit', END)
graph = graph.compile()

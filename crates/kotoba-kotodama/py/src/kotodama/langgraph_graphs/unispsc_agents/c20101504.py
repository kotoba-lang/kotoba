from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    spec_data: dict
    validation_passed: bool
    log: List[str]

def validate_actuator_specs(state: ActuatorState):
    specs = state.get('spec_data', {})
    passed = all(k in specs for k in ['torque', 'accuracy'])
    return {'validation_passed': passed, 'log': ['Specs validated'] if passed else ['Missing fields']}

def compile_robotics_workflow():
    workflow = StateGraph(ActuatorState)
    workflow.add_node('validate', validate_actuator_specs)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', END)
    return workflow.compile()

graph = compile_robotics_workflow()

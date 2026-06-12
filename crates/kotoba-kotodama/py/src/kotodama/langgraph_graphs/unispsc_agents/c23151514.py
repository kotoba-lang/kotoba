from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    specs: dict
    validation_passed: bool

def validate_robot_specs(state: RobotState):
    specs = state.get('specs', {})
    required = ['payload', 'reach']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def process_robot_order(state: RobotState):
    if state['validation_passed']:
        print('Proceeding to automated Procurement workflow')
    return state

builder = StateGraph(RobotState)
builder.add_node('validate', validate_robot_specs)
builder.add_node('process', process_robot_order)
builder.set_entry_point('validate')
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
graph = builder.compile()

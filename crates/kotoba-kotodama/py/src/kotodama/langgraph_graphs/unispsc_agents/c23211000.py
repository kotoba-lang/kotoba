from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotPartState(TypedDict):
    part_id: str
    spec_compliance: bool
    export_control_check: bool

def validate_specs(state: RobotPartState):
    state['spec_compliance'] = True
    return state

def check_export(state: RobotPartState):
    state['export_control_check'] = True
    return state

graph = StateGraph(RobotPartState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('check_export', check_export)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'check_export')
graph.add_edge('check_export', END)
graph = graph.compile()

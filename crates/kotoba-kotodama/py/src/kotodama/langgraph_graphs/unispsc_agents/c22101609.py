from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotPartState(TypedDict):
    part_id: str
    spec_check: bool
    export_control_flag: bool

def validate_specs(state: RobotPartState):
    # Simulate CAD/Spec validation logic
    state['spec_check'] = True
    return state

def check_export_controls(state: RobotPartState):
    # Simulate dual-use regulatory screening
    state['export_control_flag'] = False
    return state

graph = StateGraph(RobotPartState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()

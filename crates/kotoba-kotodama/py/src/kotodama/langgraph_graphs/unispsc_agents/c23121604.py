from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    part_number: str
    spec_check: bool
    export_cleared: bool

def validate_specs(state: RobotState):
    state['spec_check'] = True
    return state

def check_export_compliance(state: RobotState):
    state['export_cleared'] = True
    return state

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

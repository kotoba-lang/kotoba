from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    spec_sheet: dict
    validation_log: list
    is_compliant: bool

def validate_robot_specs(state: RobotProcurementState):
    log = []
    specs = state.get('spec_sheet', {})
    if specs.get('load_capacity', 0) <= 0:
        log.append('Invalid load capacity')
    return {'validation_log': log, 'is_compliant': len(log) == 0}

graph = StateGraph(RobotProcurementState)
graph.add_node('validate', validate_robot_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    part_id: str
    specs: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: RobotState):
    specs = state.get('specs', {})
    passed = all([k in specs for k in ['load_capacity_kg', 'repeatability_mm']])
    return {'validation_passed': passed, 'log': [f'Specs validation: {passed}']}

def process_motion_control(state: RobotState):
    return {'log': state.get('log', []) + ['Processing motion control parameters...']}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_motion_control)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

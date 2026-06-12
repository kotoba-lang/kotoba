from typing import TypedDict
from langgraph.graph import StateGraph, END

class MountingBoardState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_board_specs(state: MountingBoardState):
    specs = state.get('spec_data', {})
    required = ['thickness_mm', 'material_composition']
    valid = all(key in specs for key in required)
    return {'validation_passed': valid}

def route_by_validation(state: MountingBoardState):
    return 'valid' if state['validation_passed'] else 'invalid'

graph = StateGraph(MountingBoardState)
graph.add_node('validate', validate_board_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

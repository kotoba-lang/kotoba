from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastleNutState(TypedDict):
    part_specs: dict
    validation_passed: bool
    errors: List[str]

def validate_specs(state: CastleNutState):
    specs = state.get('part_specs', {})
    errors = []
    if 'thread' not in specs: errors.append('Missing thread pitch.')
    if 'material' not in specs: errors.append('Missing material grade.')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

def route_verification(state: CastleNutState):
    return 'valid' if state['validation_passed'] else 'invalid'

graph = StateGraph(CastleNutState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

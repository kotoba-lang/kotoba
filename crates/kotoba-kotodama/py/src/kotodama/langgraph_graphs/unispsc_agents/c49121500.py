from typing import TypedDict
from langgraph.graph import StateGraph, END

class OutdoorGearState(TypedDict):
    gear_id: str
    spec_data: dict
    validation_passed: bool

def validate_gear(state: OutdoorGearState):
    specs = state.get('spec_data', {})
    is_valid = 'water_resistance_rating' in specs and 'safety_certification' in specs
    return {'validation_passed': is_valid}

def route_gear(state: OutdoorGearState):
    return 'valid' if state['validation_passed'] else 'flagged'

graph = StateGraph(OutdoorGearState)
graph.add_node('validate', validate_gear)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()

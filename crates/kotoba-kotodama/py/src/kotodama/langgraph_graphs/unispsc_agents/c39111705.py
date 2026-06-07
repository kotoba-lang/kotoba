from typing import TypedDict
from langgraph.graph import StateGraph, END

class LightStickState(TypedDict):
    batch_id: str
    is_expired: bool
    brightness_test_passed: bool

def check_shelf_life(state: LightStickState):
    return {'is_expired': False}

def validate_luminosity(state: LightStickState):
    return {'brightness_test_passed': True}

graph = StateGraph(LightStickState)
graph.add_node('check_shelf_life', check_shelf_life)
graph.add_node('validate_luminosity', validate_luminosity)
graph.set_entry_point('check_shelf_life')
graph.add_edge('check_shelf_life', 'validate_luminosity')
graph.add_edge('validate_luminosity', END)
graph = graph.compile()

from typing import TypedDict
from langgraph.graph import StateGraph, END

class TapeState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_resin_specs(state: TapeState):
    specs = state.get('spec_data', {})
    required = ['resin_content_percentage', 'shelf_life_expiry']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'error_log': [] if passed else ['Missing technical specs']}

def check_shelf_life(state: TapeState):
    if state['validation_passed'] and state['spec_data'].get('shelf_life_expiry', 0) < 6:
        state['error_log'].append('Critical: Shelf life below 6 months')
        state['validation_passed'] = False
    return state

graph = StateGraph(TapeState)
graph.add_node('validate', validate_resin_specs)
graph.add_node('check_life', check_shelf_life)
graph.set_entry_point('validate')
graph.add_edge('validate', 'check_life')
graph.add_edge('check_life', END)
graph = graph.compile()

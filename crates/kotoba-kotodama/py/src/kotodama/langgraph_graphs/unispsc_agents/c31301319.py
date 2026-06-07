from typing import TypedDict
from langgraph.graph import StateGraph, END

class DieState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_dimensions(state: DieState):
    specs = state.get('spec_data', {})
    is_valid = 'tolerance' in specs and 'dimensions' in specs
    return {'validation_passed': is_valid, 'error_log': [] if is_valid else ['Missing tolerances']}

def process_forging(state: DieState):
    return {'error_log': state['error_log'] + ['Forging parameters validated']}

graph = StateGraph(DieState)
graph.add_node('val', validate_dimensions)
graph.add_node('proc', process_forging)
graph.set_entry_point('val')
graph.add_edge('val', 'proc')
graph.add_edge('proc', END)
graph = graph.compile()

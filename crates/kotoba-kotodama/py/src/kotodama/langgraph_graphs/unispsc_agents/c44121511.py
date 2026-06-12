from typing import TypedDict
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    order_id: str
    specs: dict
    validation_passed: bool

def validate_specs(state: PackagingState):
    required = ['inner_dimensions_mm', 'board_grade_and_flute_type']
    state['validation_passed'] = all(k in state.get('specs', {}) for k in required)
    return state

def check_durability(state: PackagingState):
    if state.get('validation_passed'):
        print('Performing structural integrity analysis...')
    return state

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_specs)
graph.add_node('durability', check_durability)
graph.set_entry_point('validate')
graph.add_edge('validate', 'durability')
graph.add_edge('durability', END)
graph = graph.compile()

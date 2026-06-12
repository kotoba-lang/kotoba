from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoffeeGrinderState(TypedDict):
    specs: dict
    validation_results: list
    is_compliant: bool

def validate_grinder(state: CoffeeGrinderState):
    specs = state.get('specs', {})
    results = []
    if 'power_rating' not in specs:
        results.append('Missing power rating')
    state['validation_results'] = results
    state['is_compliant'] = len(results) == 0
    return state

graph = StateGraph(CoffeeGrinderState)
graph.add_node('validate', validate_grinder)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CoffeeGrinderState(TypedDict):
    model_specs: dict
    validation_errors: List[str]
    approved: bool

def validate_commercial_standards(state: CoffeeGrinderState) -> CoffeeGrinderState:
    specs = state.get('model_specs', {})
    errors = []
    if 'burr_type' not in specs: errors.append('Missing burr material')
    if specs.get('capacity', 0) < 5: errors.append('Capacity below commercial threshold')
    state['validation_errors'] = errors
    state['approved'] = len(errors) == 0
    return state

graph = StateGraph(CoffeeGrinderState)
graph.add_node('validate', validate_commercial_standards)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

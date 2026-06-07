from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ServoState(TypedDict):
    specs: dict
    validation_results: List[str]
    approved: bool

def validate_specs(state: ServoState) -> ServoState:
    specs = state.get('specs', {})
    results = []
    if specs.get('torque_rating_nm', 0) <= 0:
        results.append('Invalid torque rating')
    state['validation_results'] = results
    state['approved'] = len(results) == 0
    return state

graph = StateGraph(ServoState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

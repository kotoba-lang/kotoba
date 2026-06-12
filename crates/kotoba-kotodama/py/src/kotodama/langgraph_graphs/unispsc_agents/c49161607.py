from typing import TypedDict
from langgraph.graph import StateGraph, END

class RacquetState(TypedDict):
    specs: dict
    is_validated: bool

def validate_specs(state: RacquetState):
    s = state.get('specs', {})
    weight = s.get('weight', 0)
    state['is_validated'] = 250 <= weight <= 350
    return state

def check_compliance(state: RacquetState):
    return 'valid' if state.get('is_validated') else 'invalid'

graph = StateGraph(RacquetState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

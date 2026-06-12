from typing import TypedDict
from langgraph.graph import StateGraph, END

class TeaState(TypedDict):
    batch_id: str
    expiration_date: str
    safety_check: bool
    approved: bool

def validate_batch(state: TeaState):
    # Business logic for batch validation
    state['safety_check'] = True if state.get('batch_id') else False
    return state

def finalize_check(state: TeaState):
    state['approved'] = state['safety_check']
    return state

graph = StateGraph(TeaState)
graph.add_node('validate', validate_batch)
graph.add_node('finalize', finalize_check)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()

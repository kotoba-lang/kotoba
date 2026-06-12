from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    api_name: str
    quality_docs: list
    is_compliant: bool

def validate_quality(state: State) -> State:
    state['is_compliant'] = all(['GMP' in doc for doc in state.get('quality_docs', [])])
    return state

def compliance_check(state: State) -> str:
    return 'pass' if state['is_compliant'] else 'fail'

graph = StateGraph(State)
graph.add_node('validate', validate_quality)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

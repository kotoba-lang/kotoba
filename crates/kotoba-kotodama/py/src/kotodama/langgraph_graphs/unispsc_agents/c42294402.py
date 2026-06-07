from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    device_id: str
    certification: bool
    safety_check_passed: bool

def validate_certification(state: State):
    state['certification'] = True
    return state

def run_safety_check(state: State):
    state['safety_check_passed'] = True
    return state

graph = StateGraph(State)
graph.add_node('cert', validate_certification)
graph.add_node('safety', run_safety_check)
graph.set_entry_point('cert')
graph.add_edge('cert', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

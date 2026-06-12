from typing import TypedDict
from langgraph.graph import StateGraph, END

class BodyLanguageState(TypedDict):
    material_type: str
    validation_passed: bool

def validate_content(state: BodyLanguageState):
    # Simulate review of instructional material criteria
    state['validation_passed'] = 'author_credentials' in state
    return state

def route_by_type(state: BodyLanguageState):
    return 'content_check' if state['material_type'] == 'video' else END

graph = StateGraph(BodyLanguageState)
graph.add_node('content_check', validate_content)
graph.add_edge('content_check', END)
graph.set_entry_point('content_check')

graph = graph.compile()

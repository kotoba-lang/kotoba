from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ContentState(TypedDict):
    material_id: str
    content_type: str
    is_vetted: bool

def validate_content(state: ContentState):
    state['is_vetted'] = state.get('content_type') in ['psychological', 'academic', 'career']
    return state

def route_distribution(state: ContentState):
    return 'publish' if state['is_vetted'] else 'review'

graph = StateGraph(ContentState)
graph.add_node('validate', validate_content)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
